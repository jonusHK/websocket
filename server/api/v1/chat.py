import asyncio
import base64
import json
import logging
from datetime import datetime
from io import BytesIO
from typing import List, Set, Coroutine, Dict, Any

from aioredis import Redis
from aioredis.client import PubSub
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import HTMLResponse

from server.api import ExceptionHandlerRoute, templates
from server.api.common import AuthValidator, RedisHandler
from server.core.authentications import cookie, RoleChecker
from server.core.enums import UserType, ChatType
from server.core.exceptions import ExceptionHandler
from server.core.externals.redis import AioRedis
from server.core.externals.redis.schemas import RedisUserProfilesByRoomS, \
    RedisChatHistoriesByRoomS, RedisChatHistoriesToSyncS, RedisUserProfileByRoomS, RedisChatHistoryByRoomS, \
    RedisChatRoomsByUserProfileS, RedisChatRoomByUserProfileS, RedisChatHistoryFileS, RedisUserImageFileS
from server.crud.service import ChatRoomUserAssociationCRUD, ChatRoomCRUD, ChatHistoryCRUD, \
    ChatHistoryUserAssociationCRUD
from server.crud.user import UserProfileCRUD
from server.db.databases import get_async_session, settings
from server.models import User, UserProfile, ChatRoom, ChatRoomUserAssociation, ChatHistory, \
    ChatHistoryUserAssociation, ChatHistoryFile, UserProfileImage
from server.schemas.base import WebSocketFileS
from server.schemas.chat import ChatSendFormS, ChatSendDataS, ChatReceiveFormS, ChatRoomCreateParamS
from server.schemas.service import ChatRoomS

router = APIRouter(route_class=ExceptionHandlerRoute)

logger = logging.getLogger("chat")


@router.get("", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/rooms", response_class=HTMLResponse)
async def rooms(request: Request):
    return templates.TemplateResponse("rooms.html", {"request": request})


@router.post(
    "/rooms/create",
    dependencies=[Depends(cookie), Depends(RoleChecker([UserType.USER]))],
    response_model=ChatRoomS)
async def chat_room_create(
    data: ChatRoomCreateParamS,
    session: AsyncSession = Depends(get_async_session),
    request_user: User = Depends(RoleChecker([UserType.USER]))
):
    """
    대화방 생성
    1) 1:1
    2) 1:N
    """
    crud_user_profile = UserProfileCRUD(session)
    crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)
    crud_room = ChatRoomCRUD(session)
    redis: Redis = AioRedis().redis
    redis_handler = RedisHandler(redis)

    user_profile: UserProfile = await crud_user_profile.get(
        conditions=(
            UserProfile.id == data.user_profile_id,
            UserProfile.is_active == 1))
    if user_profile.user.id != request_user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized user profile.")
    target_profiles: List[UserProfile] = await crud_user_profile.list(conditions=(
        UserProfile.id.in_(data.target_profile_ids),
        UserProfile.is_active == 1))
    if len(data.target_profile_ids) != len(target_profiles):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Not exists all for target profile ids.")

    mapping_profile_ids = data.target_profile_ids + [data.user_profile_id]

    # 1:1 방 생성 시, 기존 방 있다면 리턴
    if len(data.target_profile_ids) == 1:
        room_mapping = await crud_room_user_mapping.list(
            join=[(ChatRoom, ChatRoomUserAssociation.room_id == ChatRoom.id)],
            with_only_columns=(
                ChatRoom,
                func.count(ChatRoomUserAssociation.user_profile_id).label('profile_cnt')),
            conditions=(
                ChatRoom.is_active == 1,
                ChatRoomUserAssociation.user_profile_id.in_(mapping_profile_ids)),
            group_by=(ChatRoomUserAssociation.room_id,),
            having=(func.count(ChatRoomUserAssociation.user_profile_id) == len(mapping_profile_ids)))
        if room_mapping:
            return ChatRoomS.from_orm(room_mapping[-1])

    # 유저와 대화방 매핑
    default_room_name: str = ", ".join([user_profile.nickname] + [profile.nickname for profile in target_profiles])
    room: ChatRoom = await crud_room.create(name=default_room_name)
    await session.flush()
    await session.refresh(room)
    profile_ids: List[int] = [data.user_profile_id] + data.target_profile_ids
    room_user_mappings_db = [ChatRoomUserAssociation(
        room_id=room.id, user_profile_id=profile_id) for profile_id in profile_ids]
    session.add_all(room_user_mappings_db)
    await session.commit()

    # Redis 데이터 업데이트
    for o in room_user_mappings_db:
        await session.refresh(o)
        await RedisUserProfilesByRoomS.sadd(
            redis, room.id, RedisUserProfilesByRoomS.schema(
                id=o.user_profile_id,
                nickname=o.user_profile.nickname,
                files=await redis_handler.generate_presigned_files(
                    UserProfileImage, RedisUserImageFileS, o.user_profile.images)))

        files: List[RedisUserImageFileS] = []
        for m in room.user_profiles:
            files.extend(
                await redis_handler.generate_presigned_files(
                    UserProfileImage, RedisUserImageFileS,
                    [im for im in m.user_profile.images if im.is_default]))
        await RedisChatRoomsByUserProfileS.sadd(
            redis, o.room_id, RedisChatRoomsByUserProfileS.schema(
                id=room.id,
                name=room.name,
                user_profile_files=files,
                unread_msg_cnt=0))

    return ChatRoomS.from_orm(room)


@router.websocket("/rooms/{user_profile_id}")
async def chat_room(
    websocket: WebSocket,
    user_profile_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """
    대화 방 목록 조회
    """
    crud_user_profile = UserProfileCRUD(session)
    redis: Redis = AioRedis().redis
    redis_handler = RedisHandler(redis)

    user: User = await AuthValidator(session).get_user_by_websocket(websocket)
    if not next((p for p in user.profiles if p.id == user_profile_id), None):
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

    await websocket.accept()

    while True:
        try:
            while True:
                rooms_redis: List[RedisChatRoomByUserProfileS] = \
                    await RedisChatRoomsByUserProfileS.smembers(redis, user_profile_id)
                if rooms_redis:
                    break
                user_profile: UserProfile = await crud_user_profile.get(
                    conditions=(UserProfile.id == user_profile_id,))
                if not user_profile:
                    raise WebSocketDisconnect(
                        code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                        reason=f"Not exist user profile.")
                if not user_profile.rooms:
                    rooms_redis = []
                    break

                rooms_redis = []
                for m in user_profile.rooms:
                    files: List[RedisUserImageFileS] = []
                    for p in m.room.user_profiles:
                        files.extend(
                            await redis_handler.generate_presigned_files(
                                UserProfileImage, RedisUserImageFileS, p.images)
                        )
                    rooms_redis.append(
                        RedisChatRoomsByUserProfileS.schema(
                            id=m.room.id, name=m.room.name, user_profile_files=files, unread_msg_cnt=0))
                await RedisChatRoomsByUserProfileS.sadd(redis, user_profile_id, *rooms_redis)

            result = []
            if rooms_redis:
                for room_redis in rooms_redis:
                    obj: Dict[str, Any] = jsonable_encoder(room_redis)
                    # 마지막 대화 내역 업데이트
                    chat_histories: List[RedisChatHistoryByRoomS] = \
                        await RedisChatHistoriesByRoomS.zrevrange(redis, room_redis.id, 0, 1)
                    if chat_histories:
                        obj.update({
                            'last_chat_history': jsonable_encoder(chat_histories[0])
                        })
                    result.append(obj)

            await websocket.send_json(result)
        except WebSocketDisconnect as e:
            logger.exception(e)
            raise e
        except Exception as e:
            logger.exception(e)


@router.websocket("/{user_profile_id}/{room_id}")
async def chat(
    websocket: WebSocket,
    user_profile_id: int,
    room_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    대화 방 입장 및 실시간 채팅
    """
    def get_log_error(exc: Exception):
        return f"Chat Error - room_id: {room_id}, user_profile_id: {user_profile_id}, " \
               f"reason: {ExceptionHandler(exc).error}"

    user: User = await AuthValidator(session).get_user_by_websocket(websocket)
    if not next((p for p in user.profiles if p.id == user_profile_id), None):
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

    now = datetime.now().astimezone()
    redis: Redis = AioRedis().redis
    redis_handler = RedisHandler(redis)

    crud_room = ChatRoomCRUD(session)
    crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)
    crud_chat_history = ChatHistoryCRUD(session)
    crud_history_user_mapping = ChatHistoryUserAssociationCRUD(session)
    crud_user_profile = UserProfileCRUD(session)

    try:
        # 방 존재 여부 확인
        try:
            while True:
                rooms_redis: List[RedisChatRoomByUserProfileS] = \
                    await RedisChatRoomsByUserProfileS.smembers(redis, user_profile_id)
                room_redis = next((r for r in rooms_redis if r.id == room_id), None) if rooms_redis else None
                if room_redis:
                    break
                room_db: ChatRoom = await crud_room.get(conditions=(
                    ChatRoom.id == room_id,
                    ChatRoom.is_active == 1))
                if not room_db.user_profiles:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No users for room')
                await RedisChatRoomsByUserProfileS.sadd(redis, user_profile_id, *[
                    RedisChatRoomsByUserProfileS.schema(
                        id=m.room_id,
                        name=m.room.name,
                        user_profile_files=await redis_handler.generate_presigned_files(
                            UserProfileImage, RedisUserImageFileS, m.user_profile.images),
                        unread_msg_cnt=0) for m in room_db.user_profiles])
        except Exception as e:
            raise WebSocketDisconnect(
                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                reason=f"Not exist room. {e}")

        while True:
            user_profiles_redis: List[RedisUserProfileByRoomS] = \
                await RedisUserProfilesByRoomS.smembers(redis, room_id)
            if user_profiles_redis:
                break
            room_user_mapping: List[ChatRoomUserAssociation] = \
                await crud_room_user_mapping.list(conditions=(
                    ChatRoomUserAssociation.room_id == room_id,
                    ChatRoomUserAssociation.user_profile_id == user_profile_id))
            if not room_user_mapping:
                user_profiles_redis = []
                break
            await RedisUserProfilesByRoomS.sadd(redis, room_id, *[
                RedisUserProfilesByRoomS.schema(
                    id=p.user_profile.id,
                    nickname=p.user_profile.nickname,
                    files=await redis_handler.generate_presigned_files(UserProfileImage, RedisUserImageFileS, p.user_profile.images)
                ) for p in room_user_mapping])

        # 방에 유저들이 접속되어 있는지 확인
        if not user_profiles_redis:
            raise WebSocketDisconnect(
                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                reason="Not exist any user in the room.")
        # 방에 해당 유저가 접속되어 있는지 확인
        user_profile = next((p for p in user_profiles_redis if p.id == user_profile_id), None)
        if not user_profile:
            raise WebSocketDisconnect(
                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                reason="Not exist the user in the room.")

    except Exception as e:
        code = e.code if isinstance(e, WebSocketDisconnect) else status.WS_1006_ABNORMAL_CLOSURE
        logger.exception(get_log_error(e))
        await websocket.close(code=code)
        raise WebSocketDisconnect(code=code, reason=ExceptionHandler(e).error)

    await websocket.accept()

    async def producer_handler(pub: Redis, ws: WebSocket):
        try:
            while True:
                data = await ws.receive_json()
                if not data:
                    continue
                try:
                    user_profiles_redis: List[RedisUserProfileByRoomS] = \
                        await RedisUserProfilesByRoomS.smembers(redis, room_id)
                    if not user_profiles_redis:
                        raise WebSocketDisconnect(
                            code=status.WS_1001_GOING_AWAY,
                            reason="Not exist any user in the room.")
                    if not next((p for p in user_profiles_redis if p.id == user_profile_id), None):
                        raise WebSocketDisconnect(
                            code=status.WS_1001_GOING_AWAY,
                            reason="Left the chat room.")

                    request_s = ChatReceiveFormS(**data)

                    # 업데이트 요청
                    if request_s.type == ChatType.UPDATE:
                        if not request_s.data.history_ids:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists chat history ids.")
                        chat_histories_redis: List[RedisChatHistoryByRoomS] = \
                            await RedisChatHistoriesByRoomS.zrevrange(redis, room_id)
                        if not chat_histories_redis:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists chat histories in the room.")

                        # 업데이트 필요한 필드 확인
                        update_fields = (ChatHistory.is_active.name,)
                        _update_target_redis: List[RedisChatHistoryByRoomS] = []
                        _update_target_db: List[int] = []
                        _update_values_db: Dict[str, Any] = {}
                        for history_id in request_s.data.history_ids:
                            history: RedisChatHistoryByRoomS = next(
                                (h for h in chat_histories_redis if h.id == history_id), None)
                            _update_redis, _update_db = False, False
                            for f in update_fields:
                                if getattr(request_s.data, f) is None:
                                    continue
                                if history:
                                    if getattr(request_s.data, f) != getattr(history, f):
                                        setattr(history, f, getattr(request_s.data, f))
                                        _update_redis = True
                                else:
                                    _update_values_db.update({f: getattr(request_s.data, f)})
                                    _update_db = True
                            if _update_redis:
                                _update_target_redis.append(history)
                                await RedisChatHistoriesByRoomS.zrem(redis, room_id, history)
                            if _update_db:
                                _update_target_db.append(history_id)

                        # Redis 에 저장되어 있는 객체 업데이트
                        if _update_target_redis:
                            for history in _update_target_redis:
                                await RedisChatHistoriesByRoomS.zadd(redis, room_id, history)
                                await RedisChatHistoriesToSyncS.zadd(redis, room_id, RedisChatHistoriesToSyncS.schema(
                                    id=history.id, room_id=room_id, user_profile_id=history.user_profile_id))
                        # Redis 에 저장되어 있지 않은 history_ids 에 한해 DB 업데이트
                        if _update_target_db:
                            await crud_chat_history.update(
                                values=_update_values_db,
                                conditions=(ChatHistory.id.in_(_update_target_db)))
                            await session.commit()

                        response_s = ChatSendFormS(
                            type=request_s.type,
                            data=ChatSendDataS(
                                history_ids=request_s.data.history_ids,
                                is_active=request_s.data.is_active))
                    # 메시지 요청
                    elif request_s.type == ChatType.MESSAGE:
                        # DB 저장
                        chat_history_db: ChatHistory = await crud_chat_history.create(
                            room_id=room_id,
                            user_profile_id=user_profile_id,
                            contents=request_s.data.text)
                        await session.commit()
                        await session.refresh(chat_history_db)
                        # Redis 저장
                        history_s: RedisChatHistoryByRoomS = RedisChatHistoriesByRoomS.schema(
                            id=chat_history_db.id,
                            user_profile_id=chat_history_db.user_profile_id,
                            contents=chat_history_db.contents,
                            read_user_ids=[user_profile_id],
                            timestamp=request_s.data.timestamp,
                            is_active=True)
                        await RedisChatHistoriesByRoomS.zadd(redis, room_id, history_s)
                        # 각 유저 별 해당 방의 unread_msg_cnt 업데이트
                        _user_profiles_redis: List[RedisUserProfileByRoomS] = \
                            await RedisUserProfilesByRoomS.smembers(redis, room_id)
                        if _user_profiles_redis:
                            for _user_profile in _user_profiles_redis:
                                unread_msg_cnt = 1
                                _rooms_redis: List[RedisChatRoomByUserProfileS] = \
                                    await RedisChatRoomsByUserProfileS.smembers(redis, _user_profile.id)
                                _room_redis = next(
                                    (_r for _r in _rooms_redis if _r.id == room_id), None) if _rooms_redis else None
                                if _room_redis:
                                    await RedisChatRoomsByUserProfileS.srem(redis, _user_profile.id, _room_redis)
                                    unread_msg_cnt = _room_redis.unread_msg_cnt + 1
                                await RedisChatRoomsByUserProfileS.sadd(
                                    redis, _user_profile.id, RedisChatRoomsByUserProfileS.schema(
                                        id=room_id,
                                        name=room_redis.name,
                                        user_profile_files=room_redis.user_profile_files,
                                        unread_msg_cnt=unread_msg_cnt))

                        response_s = ChatSendFormS(
                            type=request_s.type,
                            data=ChatSendDataS(
                                user_profile_id=user_profile_id,
                                nickname=user_profile.nickname,
                                timestamp=request_s.data.timestamp,
                                text=request_s.data.text,
                                is_active=request_s.data.is_active))
                    # 파일 업로드 요청
                    elif request_s.type == ChatType.FILE:
                        chat_history_db: ChatHistory = await crud_chat_history.create(
                            room_id=room_id, user_profile_id=user_profile_id)
                        await session.flush()
                        await session.refresh(chat_history_db)
                        chat_files_db: List[ChatHistoryFile] = []
                        _idx = 1

                        converted_files = [
                            WebSocketFileS(
                                content=BytesIO(base64.b64decode(f.content)),
                                filename=f.filename,
                                content_type=f.content_type
                            ) for f in request_s.data.files
                        ]
                        async for o in ChatHistoryFile.files_to_models(
                                session,
                                converted_files,
                                root='chat_upload/',
                                user_profile_id=user_profile_id,
                                bucket_name=settings.aws_storage_bucket_name,
                        ):
                            o.chat_history_id = chat_history_db.id
                            o.order = _idx
                            chat_files_db.append(o)
                            _idx += 1

                        try:
                            if len(chat_files_db) == 1:
                                await chat_files_db[0].upload()
                            else:
                                await ChatHistoryFile.asynchronous_upload(*chat_files_db)
                            session.add_all(chat_files_db)
                            await session.commit()
                        finally:
                            for o in chat_files_db:
                                o.close()
                                await session.refresh(o)

                        files_s: List[RedisChatHistoryFileS] = await redis_handler.generate_presigned_files(
                            ChatHistoryFile, RedisChatHistoryFileS, chat_files_db)
                        await RedisChatHistoriesByRoomS.zadd(redis, room_id, RedisChatHistoriesByRoomS.schema(
                            id=chat_history_db.id,
                            user_profile_id=user_profile_id,
                            files=files_s,
                            timestamp=request_s.data.timestamp,
                            is_active=chat_history_db.is_active))

                        response_s = ChatSendFormS(
                            type=request_s.type,
                            data=ChatSendDataS(
                                user_profile_id=user_profile_id,
                                nickname=user_profile.nickname,
                                files=files_s,
                                timestamp=request_s.data.timestamp,
                                is_active=chat_history_db.is_active))
                    # 대화 내용 조회
                    elif request_s.type == ChatType.LOOKUP:
                        if not request_s.data.offset or not request_s.data.limit:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists offset or limit for page.")

                        # 해당 방의 unread_msg_cnt = 0 설정
                        rooms_by_profile: List[RedisChatRoomByUserProfileS] = \
                            await RedisChatRoomsByUserProfileS.smembers(redis, user_profile_id)
                        for r in rooms_by_profile:
                            if r.id == room_id:
                                await RedisChatRoomsByUserProfileS.srem(redis, user_profile_id, r)
                                break
                        await RedisChatRoomsByUserProfileS.sadd(
                            redis, user_profile_id, RedisChatRoomsByUserProfileS.schema(
                                id=room_id,
                                name=room_redis.name,
                                user_profile_files=room_redis.user_profile_files,
                                unread_msg_cnt=0))
                        # Redis 에서 대화 내용 조회
                        chat_histories_redis: List[RedisChatHistoryByRoomS] = \
                            await RedisChatHistoriesByRoomS.zrevrange(
                                redis, room_id,
                                start=request_s.data.offset,
                                end=request_s.data.offset + request_s.data.limit - 1)
                        # Redis 에 데이터 없는 경우 DB 에서 조회
                        lack_cnt: int = request_s.data.limit - len(chat_histories_redis)
                        if lack_cnt > 0:
                            if chat_histories_redis:
                                next_offset: int = request_s.data.offset + len(chat_histories_redis) + 1
                            else:
                                next_offset: int = request_s.data.offset
                            chat_histories_db: List[ChatHistory] = await crud_chat_history.list(
                                offset=next_offset,
                                limit=lack_cnt,
                                order_by=(getattr(ChatHistory, request_s.data.order_by).desc(),))

                            add_chat_histories: List[RedisChatHistoryByRoomS] = [
                                RedisChatHistoriesByRoomS.schema(
                                        id=h.id,
                                        user_profile_id=h.user_profile_id,
                                        contents=h.contents,
                                        files=await redis_handler.generate_presigned_files(
                                            UserProfileImage, RedisUserImageFileS, h.user_profile.images),
                                        read_user_ids=[
                                            m.user_profile_id for m in h.user_profile_mapping if m.is_read
                                        ] if h.user_profile_mapping else [],
                                        timestamp=h.created,
                                        is_active=h.is_active
                                ) for h in chat_histories_db
                            ]

                            # 채팅 읽은 유저의 DB 정보 업데이트
                            if chat_histories_db:
                                _create_target_db: List[ChatHistory] = []
                                _update_target_db: List[ChatHistoryUserAssociation] = []
                                for h in chat_histories_db:
                                    if not h.user_profile_mapping:
                                        _create_target_db.append(h)
                                    else:
                                        _is_exists = False
                                        for m in h.user_profile_mapping.all():
                                            if m.user_profile_id == user_profile_id:
                                                _is_exists = True
                                                if not m.is_read:
                                                    _update_target_db.append(m)
                                        if not _is_exists:
                                            _create_target_db.append(h)
                                if _create_target_db:
                                    await crud_history_user_mapping.bulk_create([
                                        dict(
                                            history_id=h.id,
                                            user_profile_id=user_profile_id) for h in _create_target_db])
                                    await session.commit()
                                if _update_target_db:
                                    await crud_history_user_mapping.bulk_update([
                                        dict(id=m.id, is_read=True) for m in _update_target_db])
                                    await session.commit()
                        else:
                            add_chat_histories = []
                        # 요청한 채팅 정보 추출
                        chat_histories: List[RedisChatHistoryByRoomS] = chat_histories_redis + add_chat_histories
                        # Redis 채팅 읽은 유저 ids 에 user_profile_id 업데이트
                        await RedisChatHistoriesByRoomS.zrem(redis, room_id, chat_histories)
                        for history in chat_histories:
                            history.read_user_ids = list(set(history.read_user_ids) | {user_profile_id})
                        await RedisChatHistoriesByRoomS.zadd(redis, room_id, chat_histories)
                        await RedisChatHistoriesToSyncS.zadd(redis, room_id, [RedisChatHistoriesToSyncS.schema(
                            id=history.id, room_id=room_id, user_profile_id=history.user_profile_id
                        ) for history in chat_histories])
                        response_s = ChatSendFormS(
                            type=ChatType.LOOKUP,
                            data=ChatSendDataS(
                                histories=chat_histories,
                                user_profiles=await RedisUserProfilesByRoomS.smembers(redis, room_id),
                                timestamp=request_s.data.timestamp))
                    # 유저 초대
                    else:
                        while True:
                            _user_profiles_redis: List[
                                RedisUserProfileByRoomS] = await RedisUserProfilesByRoomS.smembers(redis, room_id)
                            if _user_profiles_redis:
                                break
                            _room_user_mapping: List[
                                ChatRoomUserAssociation
                            ] = await crud_room_user_mapping.list(conditions=(
                                ChatRoomUserAssociation.room_id == room_id,
                                ChatRoomUserAssociation.user_profile_id == user_profile_id))
                            if not _room_user_mapping:
                                _user_profiles_redis = []
                                break

                            await RedisUserProfilesByRoomS.sadd(redis, room_id, *[
                                RedisUserProfilesByRoomS.schema(
                                    id=p.user_profile.id,
                                    nickname=p.user_profile.nickname,
                                    files=await redis_handler.generate_presigned_files(
                                        UserProfileImage, RedisUserImageFileS, p.user_profile.images)
                                ) for p in _room_user_mapping])

                        current_profile_ids: Set[int] = {
                            p.id for p in _user_profiles_redis} if _user_profiles_redis else {user_profile_id}
                        target_user_profile_ids: List[int] = request_s.data.target_user_profile_ids
                        if not target_user_profile_ids:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists user profile ids for invite.")
                        add_profile_ids: Set[int] = set(target_user_profile_ids)
                        profile_ids: Set[int] = add_profile_ids - current_profile_ids
                        if not profile_ids:
                            continue
                        profiles = await crud_user_profile.list(conditions=(
                            UserProfile.id.in_(profile_ids),
                            UserProfile.is_active == 1))
                        if len(profiles) != len(target_user_profile_ids):
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Invalid user profile ids for invite.")
                        # Redis 업데이트
                        await RedisUserProfilesByRoomS.sadd(redis, room_id, *[
                            RedisUserProfilesByRoomS.schema(
                                id=p.id,
                                nickname=p.nickname,
                                files=await redis_handler.generate_presigned_files(
                                    UserProfileImage, RedisUserImageFileS, p.images)
                            ) for p in profiles if p.id in profile_ids
                        ])
                        # DB 업데이트
                        await crud_room_user_mapping.bulk_create([
                            dict(
                                room_id=room_id,
                                user_profile_id=profile_id) for profile_id in profile_ids])
                        await session.commit()
                        # 대화방 초대 메시지 전송
                        if len(profile_ids) > 1:
                            target_msg = '님과 '.join([p.nickname for p in profiles])
                        else:
                            target_msg = profiles[0].nickname
                        response_s = ChatSendFormS(
                            type=ChatType.MESSAGE,
                            data=ChatSendDataS(
                                text=f"{user_profile.nickname}님이 {target_msg}님을 초대했습니다.",
                                timestamp=request_s.data.timestamp))
                    await pub.publish(f"chat:{room_id}", response_s.json())
                except WebSocketDisconnect as exc:
                    raise exc
                except Exception as exc:
                    logger.error(get_log_error(exc))
        except WebSocketDisconnect as exc:
            if exc.code == status.WS_1001_GOING_AWAY:
                try:
                    for s in await RedisUserProfilesByRoomS.smembers(redis, room_id):
                        if s.id == user_profile_id:
                            await RedisUserProfilesByRoomS.srem(redis, room_id, s)
                            break
                    for s in await RedisChatRoomsByUserProfileS.smembers(redis, user_profile_id):
                        if s.id == room_id:
                            await RedisChatRoomsByUserProfileS.srem(redis, user_profile_id, s)
                            break
                    delete_conditions = (
                        ChatRoomUserAssociation.room_id == room_id,
                        ChatRoomUserAssociation.user_profile_id == user_profile_id)
                    try:
                        room_user_mapping_db = await crud_room_user_mapping.get(conditions=delete_conditions)
                    except HTTPException:
                        pass
                    else:
                        # 유저와 대화방 연결 해제
                        _room_db = room_user_mapping_db.room
                        await crud_room_user_mapping.delete(conditions=delete_conditions)
                        await session.flush()
                        await session.refresh(_room_db)
                        if not _room_db.user_profiles:
                            await crud_room.update(values={'is_active': False}, conditions=(
                                ChatRoom.id == _room_db.id,
                                ChatRoom.is_active == 1))
                        await session.commit()
                        # 유저 연결 해제 메시지 전송
                        response_s = ChatSendFormS(
                            type=ChatType.MESSAGE,
                            data=ChatSendDataS(
                                text=f"{user_profile.nickname}님이 나갔습니다.",
                                timestamp=now.timestamp()))
                        await pub.publish(f"chat:{room_id}", response_s.json())
                except Exception as _exc:
                    logger.error(_exc)
            logger.exception(get_log_error(exc))
            raise exc

    async def consumer_handler(psub: PubSub, ws: WebSocket):
        try:
            async with psub as p:
                await p.subscribe(f"chat:{room_id}")
                try:
                    while True:
                        message: dict = await p.get_message(ignore_subscribe_messages=True)
                        if message:
                            await ws.send_json(json.loads(message.get('data')))
                except asyncio.CancelledError as exc:
                    await p.unsubscribe()
                    raise exc
                except Exception as exc:
                    logger.error(get_log_error(exc))
        except asyncio.CancelledError:
            await psub.close()

    redis: Redis = AioRedis().redis
    pubsub: PubSub = redis.pubsub()

    producer_task: Coroutine = producer_handler(pub=redis, ws=websocket)
    consumer_task: Coroutine = consumer_handler(psub=pubsub, ws=websocket)
    done, pending = await asyncio.wait(
        [producer_task, consumer_task], return_when=asyncio.FIRST_COMPLETED)
    logger.info(f"Done task: {done}")
    for task in pending:
        logger.info(f"Canceling task: {task}")
        task.cancel()
