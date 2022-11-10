import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Cookie, Query, Request
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import HTMLResponse

from server.api import ExceptionHandlerRoute, templates
from server.core.authentications import cookie, RoleChecker
from server.core.enums import UserType, ChatType
from server.core.exceptions import ExceptionHandler
from server.crud.service import ChatRoomUserAssociationCRUD, ChatRoomCRUD, ChatHistoryCRUD
from server.crud.user import UserProfileCRUD
from server.db.databases import get_async_session
from server.models import service as service_models
from server.models import user as user_models
from server.schemas import chat as chat_schemas
from server.schemas import service as service_schemas

router = APIRouter(route_class=ExceptionHandlerRoute)

logger = logging.getLogger("chat")


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, key: int):
        if websocket not in self.active_connections[key]:
            await websocket.accept()
            self.active_connections[key].append(websocket)

    async def disconnect(self, websocket: WebSocket, key: int, e: WebSocketDisconnect):
        if websocket in self.active_connections[key]:
            self.active_connections[key].remove(websocket)

    async def unicast(self, data: dict, websocket: WebSocket):
        await websocket.send_json(data)

    async def broadcast(self, data: dict, key: int):
        for connection in self.active_connections[key]:
            await connection.send_json(data)


manager = ConnectionManager()


async def get_cookie(
    websocket: WebSocket,
    session: str | None = Cookie(default=None),
    token: str | None = Query(default=None)
):
    if not session and not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return session or token


@router.get("", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/rooms/create", dependencies=[Depends(cookie), Depends(RoleChecker([UserType.USER]))])
async def chat_room_create(
    data: chat_schemas.ChatRoomCreate,
    session: AsyncSession = Depends(get_async_session),
    request_user: user_models.User = Depends(RoleChecker([UserType.USER]))
):
    """
    대화방 생성
    1) 1:1
    2) 1:N
    """
    crud_user_profile = UserProfileCRUD(session)
    crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)
    crud_room = ChatRoomCRUD(session)

    user_profile = await crud_user_profile.get(
        conditions=(
            user_models.UserProfile.id == data.user_profile_id,
            user_models.UserProfile.is_active == 1))
    if user_profile.user.id != request_user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized user profile.")
    target_profiles = await crud_user_profile.list(conditions=(
        user_models.UserProfile.id.in_(data.target_profile_ids),
        user_models.UserProfile.is_active == 1))
    if len(data.target_profile_ids) != len(target_profiles):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Not exists all for target profile ids.")

    # 유저와 대화방 매핑
    default_room_name = ", ".join([user_profile.nickname] + [profile.nickname for profile in target_profiles])
    room = await crud_room.create(name=default_room_name)
    await session.flush()
    current_profile_ids = set()
    add_profile_ids = set([data.user_profile_id] + data.target_profile_ids)
    profile_ids = add_profile_ids - current_profile_ids
    if not profile_ids:
        return []
    await crud_room_user_mapping.bulk_create([
        dict(room_id=room.id, user_profile_id=profile_id) for profile_id in profile_ids])
    await session.commit()
    await session.refresh(room)

    return profile_ids


# TODO session_id 사용하여 user_profile_id 추출
@router.websocket("/{user_profile_id}/{room_id}")
async def chat(
    websocket: WebSocket,
    user_profile_id: int,
    room_id: int,
    session: AsyncSession = Depends(get_async_session),
    # cookie: str = Depends(get_cookie)
):
    """
    대화 방 입장 및 실시간 채팅
    """
    now = datetime.now().astimezone()

    crud_user_profile = UserProfileCRUD(session)
    crud_room = ChatRoomCRUD(session)
    crud_chat_history = ChatHistoryCRUD(session)
    crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)
    try:
        user_profile = await crud_user_profile.get(conditions=(
            user_models.UserProfile.id == user_profile_id,
            user_models.UserProfile.is_active == 1))
        room = await crud_room.get(conditions=(
            service_models.ChatRoom.id == int(room_id),
            service_models.ChatRoom.is_active == 1))
        room_user_mapping = [p for p in room.user_profiles]
        if not room_user_mapping:
            raise WebSocketDisconnect(
                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                reason="Not exist any user in the room.")
        if not next((mapping for mapping in room_user_mapping
                     if mapping.user_profile_id == user_profile.id), None):
            raise WebSocketDisconnect(
                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                reason="Not exist the user in the room.")
    except Exception as e:
        code = e.code if isinstance(e, WebSocketDisconnect) else status.WS_1006_ABNORMAL_CLOSURE
        await websocket.close(code=code)
        raise WebSocketDisconnect(code=code, reason=ExceptionHandler(e).error)

    # 웹소켓 연결
    await manager.connect(websocket, room.id)

    # 실시간 양방향 메시지 송수신
    try:
        while True:
            # 동일한 유저가 여러 웹소켓을 연결한 상태에서 다른 웹소켓 연결을 끊은 경우
            await session.refresh(room)
            if user_profile_id not in (p.user_profile_id for p in room.user_profiles):
                raise WebSocketDisconnect(code=status.WS_1001_GOING_AWAY, reason="Left the chat room.")

            data = await websocket.receive_json()
            request_s = chat_schemas.ChatReceiveForm(**data)
            # 업데이트 요청
            if request_s.type == ChatType.UPDATE:
                if not request_s.data.history_ids:
                    raise WebSocketDisconnect(
                        code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                        reason="Not exists chat history ids.")
                chat_histories = await crud_chat_history.list(conditions=(
                    service_models.ChatHistory.id.in_(request_s.data.history_ids)))
                chat_history_ids = [h.id for h in chat_histories]
                for v in (service_models.ChatHistory.is_active.name,):
                    if getattr(request_s.data, v) is not None:
                        await crud_chat_history.update(
                            values={v: getattr(request_s.data, v)},
                            conditions=(service_models.ChatHistory.id.in_(chat_history_ids)))
            # 메시지 요청
            elif request_s.type == ChatType.MESSAGE:
                await crud_chat_history.create(
                    room_id=room_id,
                    user_profile_id=user_profile_id,
                    contents=request_s.data.text)
            # 파일 요청
            elif request_s.type == ChatType.FILE:
                await crud_chat_history.bulk_create(values=[
                    dict(
                        room_id=room_id,
                        user_profile_id=user_profile_id,
                        s3_media_id=_id
                    ) for _id in request_s.data.file_ids])
            # 대화내용 조회
            elif request_s.type == ChatType.LOOKUP:
                if not request_s.data.offset or not request_s.data.limit:
                    raise WebSocketDisconnect(
                        code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                        reason="Not exists offset or limit for page.")
                chat_histories = await crud_chat_history.list(
                    offset=request_s.data.offset,
                    limit=request_s.data.limit,
                    order_by=(getattr(service_models.ChatHistory, request_s.data.order_by),),
                    conditions=(service_models.ChatHistory.is_active == 1,))
                response_s = chat_schemas.ChatSendForm(
                    type=ChatType.LOOKUP,
                    data=chat_schemas.ChatSendData(
                        user_profile_id=user_profile_id,
                        nickname=user_profile.nickname,
                        histories=[
                            service_schemas.ChatHistory.from_orm(h) for h in chat_histories],
                        timestamp=now.timestamp()))
                await manager.broadcast(response_s.dict(), room.id)
                continue
            # 유저 초대
            else:
                current_profile_ids = {m.user_profile_id for m in room_user_mapping}
                target_user_profile_ids = request_s.data.target_user_profile_ids
                if not target_user_profile_ids:
                    raise WebSocketDisconnect(
                        code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                        reason="Not exists user profile ids for invite")
                add_profile_ids = set(request_s.data.target_user_profile_ids)
                profile_ids = add_profile_ids - current_profile_ids
                if profile_ids:
                    await crud_room_user_mapping.bulk_create([
                        dict(
                            room_id=room.id, user_profile_id=profile_id
                        ) for profile_id in profile_ids])
                    await session.commit()
                    await session.refresh(room)
                    # 대화방 초대 메시지 전송
                    new_user_profiles = [m.user_profile for m in room.user_profiles if m.user_profile_id in profile_ids]
                    if len(new_user_profiles) > 1:
                        target_msg = '님과 '.join([profile.nickname for profile in new_user_profiles])
                    else:
                        target_msg = new_user_profiles[0].nickname
                    response_s = chat_schemas.ChatSendForm(
                        type=ChatType.MESSAGE,
                        data=chat_schemas.ChatSendData(
                            user_profile_id=user_profile_id,
                            nickname=user_profile.nickname,
                            text=f"{user_profile.nickname}님이 {target_msg}님을 초대했습니다.",
                            timestamp=now.timestamp()
                        ))
                    await manager.broadcast(response_s.dict(), room.id)
                    continue

            await session.commit()

            response_s = chat_schemas.ChatSendForm(
                type=request_s.type,
                data=chat_schemas.ChatSendData(
                    user_profile_id=user_profile_id,
                    nickname=user_profile.nickname,
                    timestamp=now.timestamp(),
                    text=request_s.data.text,
                    history_ids=request_s.data.history_ids,
                    file_ids=request_s.data.file_ids,
                    is_active=request_s.data.is_active))
            await manager.broadcast(response_s.dict(), room_id)
    except WebSocketDisconnect as e:
        logger.warning(
            f"Error - room_id: {room.id}, user_profile_id: {user_profile_id}, "
            f"code: {e.code}, reason: {e.reason}")
        if e.code == status.WS_1001_GOING_AWAY:
            # 유저와 대화방 연결 해제
            await crud_room_user_mapping.delete(conditions=(
                service_models.ChatRoomUserAssociation.room_id == room_id,
                service_models.ChatRoomUserAssociation.user_profile_id == user_profile_id))
            await session.commit()
            # 유저 연결 해제 메시지 브로드캐스트
            response_s = chat_schemas.ChatSendForm(
                type=ChatType.MESSAGE,
                data=chat_schemas.ChatSendData(
                    text=f"{user_profile.nickname}님이 나갔습니다.",
                    timestamp=now.timestamp()))
            await manager.disconnect(websocket, room.id, e)
            await manager.broadcast(response_s.dict(), room.id)
    except Exception as e:
        logger.exception(
            f"Error - room_id: {room_id}, user_profile_id: {user_profile_id}, "
            f"reason: {e}")
