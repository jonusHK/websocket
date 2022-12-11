import asyncio
import base64
import json
import logging
from copy import deepcopy
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
from sqlalchemy.orm import joinedload, selectinload
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
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/rooms", response_class=HTMLResponse)
def rooms(request: Request):
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
            UserProfile.is_active == 1),
        options=[joinedload(UserProfile.user)]
    )
    if user_profile.user.id != request_user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
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
    room: ChatRoom = await crud_room.get(
        conditions=(ChatRoom.id == room.id,),
        options=[selectinload(ChatRoom.user_profiles)])

    profile_ids: List[int] = [data.user_profile_id] + data.target_profile_ids
    for profile_id in profile_ids:
        room.user_profiles.append(
            ChatRoomUserAssociation(room_id=room.id, user_profile_id=profile_id, room_name=default_room_name))

    await session.commit()

    # Redis 데이터 업데이트
    room: ChatRoom = await crud_room.get(
        conditions=(ChatRoom.id == room.id,),
        options=[
            selectinload(ChatRoom.user_profiles)
            .joinedload(ChatRoomUserAssociation.user_profile)
            .selectinload(UserProfile.images)
            .selectinload(UserProfile.followers)
        ])
    for profile_id in profile_ids:
        for m in room.user_profiles:
            await RedisUserProfilesByRoomS.sadd(
                redis, (room.id, profile_id), RedisUserProfilesByRoomS.schema(
                    id=m.user_profile_id,
                    nickname=m.user_profile.get_nickname_by_other(profile_id),
                    files=await redis_handler.generate_presigned_files(UserProfileImage, m.user_profile.images)))

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
                try:
                    user_profile: UserProfile = await crud_user_profile.get(
                        conditions=(UserProfile.id == user_profile_id,),
                        options=[
                            selectinload(UserProfile.rooms)
                            .joinedload(ChatRoomUserAssociation.room)
                            .selectinload(ChatRoom.user_profiles)
                            .selectinload(UserProfile.images)
                        ]
                    )
                except HTTPException:
                    raise WebSocketDisconnect(
                        code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                        reason=f"Not exist user profile.")
                if not user_profile.rooms:
                    break

                for m in user_profile.rooms:
                    files: List[RedisUserImageFileS] = []
                    for p in m.room.user_profiles:
                        if p.images:
                            files.extend(
                                await redis_handler.generate_presigned_files(
                                    UserProfileImage, [p for p in p.images if p.is_default]))
                    rooms_redis.append(
                        RedisChatRoomsByUserProfileS.schema(
                            id=m.room.id, name=m.room.get_name_by_user_profile(user_profile_id),
                            user_profile_files=files, unread_msg_cnt=0))
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
        raise WebSocketDisconnect(code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA, reason='Unauthorized user.')

    redis: Redis = AioRedis().redis
    redis_handler = RedisHandler(redis)

    crud_room = ChatRoomCRUD(session)
    crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)
    crud_chat_history = ChatHistoryCRUD(session)
    crud_history_user_mapping = ChatHistoryUserAssociationCRUD(session)
    crud_user_profile = UserProfileCRUD(session)

    try:
        # 해당 방 데이터 추출
        try:
            room_redis: RedisChatRoomByUserProfileS = await redis_handler.get_room_with_user_profile(
                room_id, user_profile_id, crud_room)
        except Exception as e:
            raise WebSocketDisconnect(
                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                reason=f"Not exist room. {e}")

        # 방에 속한 유저들 프로필 데이터 추출
        try:
            user_profiles_redis: List[RedisUserProfileByRoomS] = await redis_handler.get_user_profiles_in_room(
                room_id, user_profile_id, crud_room_user_mapping)
        except Exception as e:
            raise WebSocketDisconnect(
                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                reason=f"Failed to get user profiles in the room. {e}")

        # 방에 해당 유저 존재 여부 확인
        user_profile_redis: RedisUserProfileByRoomS = next((p for p in user_profiles_redis if p.id == user_profile_id), None)
        if not user_profile_redis:
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
                    # 해당 방 데이터 추출
                    try:
                        room_redis: RedisChatRoomByUserProfileS = await redis_handler.get_room_with_user_profile(
                            room_id, user_profile_id, crud_room)
                    except Exception as e:
                        raise WebSocketDisconnect(
                            code=status.WS_1000_NORMAL_CLOSURE,
                            reason=f"Not exist room. {e}")

                    # 방에 속한 유저들 프로필 데이터 추출
                    try:
                        _user_profiles_redis: List[RedisUserProfileByRoomS] = await redis_handler.get_user_profiles_in_room(
                            room_id, user_profile_id, crud_room_user_mapping)
                    except Exception as e:
                        raise WebSocketDisconnect(
                            code=status.WS_1000_NORMAL_CLOSURE,
                            reason=f"Failed to get user profiles in the room. {e}")

                    # 방에 해당 유저 존재 여부 확인
                    _user_profile_redis: RedisUserProfileByRoomS = next(
                        (p for p in _user_profiles_redis if p.id == user_profile_id), None)
                    if not _user_profile_redis:
                        raise WebSocketDisconnect(
                            code=status.WS_1000_NORMAL_CLOSURE,
                            reason="Left the chat room.")

                    # 요청 데이터 확보
                    request_s = ChatReceiveFormS(**data)

                    # 업데이트 요청
                    if request_s.type == ChatType.UPDATE:
                        if not request_s.data.history_ids:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists chat history ids.")
                        _chat_histories_redis: List[RedisChatHistoryByRoomS] = \
                            await RedisChatHistoriesByRoomS.zrevrange(redis, room_id)
                        if not _chat_histories_redis:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists chat histories in the room.")
                        # 업데이트 필요한 필드 확인
                        _update_fields = (ChatHistory.is_active.name,)
                        _update_target_redis: List[RedisChatHistoryByRoomS] = []
                        _update_target_db: List[int] = []
                        _update_values_db: Dict[str, Any] = {}
                        for _history_id in request_s.data.history_ids:
                            _history: RedisChatHistoryByRoomS = next((
                                h for h in _chat_histories_redis if h.id == _history_id), None)
                            _update_history: RedisChatHistoryByRoomS = deepcopy(_history)
                            _update_redis, _update_db = False, False
                            for f in _update_fields:
                                if getattr(request_s.data, f) is None:
                                    continue
                                if _history:
                                    # 기존 데이터와 다른 경우 업데이트 설정
                                    if getattr(request_s.data, f) != getattr(_history, f):
                                        setattr(_update_history, f, getattr(request_s.data, f))
                                        _update_redis = True
                                else:
                                    _update_values_db.update({f: getattr(request_s.data, f)})
                                    _update_db = True
                            if _update_redis:
                                _update_target_redis.append(_update_history)
                                await RedisChatHistoriesByRoomS.zrem(redis, room_id, _history)
                            if _update_db:
                                _update_target_db.append(_history_id)
                        # Redis 에 저장되어 있는 데이터 업데이트
                        if _update_target_redis:
                            await redis_handler.update_histories_by_room(room_id, _update_target_redis)
                        # Redis 에 저장되어 있지 않은 history_ids 에 한해 DB 업데이트
                        if _update_target_db:
                            await crud_chat_history.update(
                                values=_update_values_db,
                                conditions=(ChatHistory.id.in_(_update_target_db),))
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
                        await RedisChatHistoriesByRoomS.zadd(redis, room_id, RedisChatHistoriesByRoomS.schema(
                            id=chat_history_db.id,
                            user_profile_id=chat_history_db.user_profile_id,
                            contents=chat_history_db.contents,
                            read_user_ids=[user_profile_id],
                            timestamp=request_s.data.timestamp,
                            is_active=True))
                        # 각 유저 별 해당 방의 unread_msg_cnt 업데이트
                        for _user_profile in _user_profiles_redis:
                            _unread_msg_cnt = 1
                            _rooms_redis: List[RedisChatRoomByUserProfileS] = \
                                await RedisChatRoomsByUserProfileS.smembers(redis, _user_profile.id)
                            _room_redis = next((
                                _r for _r in _rooms_redis if _r.id == room_id), None) if _rooms_redis else None
                            if _room_redis:
                                await RedisChatRoomsByUserProfileS.srem(redis, _user_profile.id, _room_redis)
                                _unread_msg_cnt = _room_redis.unread_msg_cnt + 1
                            await RedisChatRoomsByUserProfileS.sadd(
                                redis, _user_profile.id, RedisChatRoomsByUserProfileS.schema(
                                    id=room_id,
                                    name=room_redis.name,
                                    user_profile_files=room_redis.user_profile_files,
                                    unread_msg_cnt=_unread_msg_cnt))
                        response_s = ChatSendFormS(
                            type=request_s.type,
                            data=ChatSendDataS(
                                user_profile_id=user_profile_id,
                                nickname=_user_profile_redis.nickname,
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
                            ChatHistoryFile, chat_files_db)
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
                                nickname=_user_profile_redis.nickname,
                                files=files_s,
                                timestamp=request_s.data.timestamp,
                                is_active=chat_history_db.is_active))
                    # 대화 내용 조회
                    elif request_s.type == ChatType.LOOKUP:
                        if not request_s.data.offset or not request_s.data.limit:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists offset or limit for page.")

                        # 해당 방의 unread_msg_cnt = 0 설정 (채팅방 접속 시, 0으로 초기화)
                        await RedisChatRoomsByUserProfileS.srem(redis, user_profile_id, room_redis)
                        room_redis.unread_msg_cnt = 0
                        await RedisChatRoomsByUserProfileS.sadd(redis, user_profile_id, room_redis)
                        # Redis 대화 내용 조회
                        chat_histories_redis: List[RedisChatHistoryByRoomS] = \
                            await RedisChatHistoriesByRoomS.zrevrange(
                                redis, room_id,
                                start=request_s.data.offset + 1,
                                end=request_s.data.offset + request_s.data.limit)
                        # Redis 데이터 없는 경우 DB 조회
                        lack_cnt: int = request_s.data.limit - len(chat_histories_redis)
                        if lack_cnt > 0:
                            if chat_histories_redis:
                                next_offset: int = request_s.data.offset + len(chat_histories_redis) + 1
                            else:
                                next_offset: int = request_s.data.offset
                            chat_histories_db: List[ChatHistory] = await crud_chat_history.list(
                                conditions=(ChatHistory.room_id == room_id,
                                            ChatHistory.user_profile_id == user_profile_id),
                                offset=next_offset,
                                limit=lack_cnt,
                                order_by=ChatHistory.generate_order_by_from_str(request_s.data.order_by),
                                options=[selectinload(ChatHistory.user_profile_mapping)]
                            )
                            # 채팅 읽은 유저의 DB 정보 업데이트 및 생성
                            if chat_histories_db:
                                _create_target_db: List[ChatHistory] = []
                                _update_target_db: List[ChatHistoryUserAssociation] = []
                                for h in chat_histories_db:
                                    if not h.user_profile_mapping:
                                        _create_target_db.append(h)
                                    else:
                                        m = next((m for m in h.user_profile_mapping
                                                  if m.user_profile_id == user_profile_id), None)
                                        if m:
                                            if not m.is_read:
                                                _update_target_db.append(m)
                                        else:
                                            _create_target_db.append(h)
                                if _create_target_db:
                                    await crud_history_user_mapping.bulk_create([
                                        dict(history_id=h.id,
                                             user_profile_id=user_profile_id) for h in _create_target_db])
                                    await session.commit()
                                if _update_target_db:
                                    await crud_history_user_mapping.bulk_update([
                                        dict(id=m.id, is_read=True) for m in _update_target_db])
                                    await session.commit()

                        # Redis 채팅 읽은 유저 ids 에 user_profile_id 업데이트
                        if chat_histories_redis:
                            await RedisChatHistoriesByRoomS.zrem(redis, room_id, chat_histories_redis)
                            for history in chat_histories_redis:
                                history.read_user_ids = list(set(history.read_user_ids) | {user_profile_id})
                            await redis_handler.update_histories_by_room(room_id, chat_histories_redis)
                        response_s = ChatSendFormS(
                            type=ChatType.LOOKUP,
                            data=ChatSendDataS(
                                histories=chat_histories_redis,
                                user_profiles=await RedisUserProfilesByRoomS.smembers(
                                    redis, (room_id, user_profile_id)),
                                timestamp=request_s.data.timestamp))
                    # 유저 초대
                    else:
                        target_user_profile_ids: List[int] = request_s.data.target_user_profile_ids
                        if not target_user_profile_ids:
                            raise WebSocketDisconnect(
                                code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                reason="Not exists user profile ids for invite.")
                        _room_user_mapping: List[ChatRoomUserAssociation] = \
                            await crud_room_user_mapping.list(
                                conditions=(
                                    ChatRoomUserAssociation.room_id == room_id,),
                                options=[
                                    joinedload(ChatRoomUserAssociation.room),
                                    joinedload(ChatRoomUserAssociation.user_profile)
                                    .selectinload(UserProfile.images),
                                    joinedload(ChatRoomUserAssociation.user_profile)
                                    .selectinload(UserProfile.followers)
                                ]
                            )
                        # 방에 속한 유저 데이터 -> Redis, DB 동기화
                        current_profile_ids: Set[int] = {m.user_profile_id for m in _room_user_mapping}
                        for current_id in current_profile_ids:
                            _user_profiles_redis = await RedisUserProfilesByRoomS.smembers(redis, (room_id, current_id))
                            if len(_user_profiles_redis) != len(_room_user_mapping):
                                for r in _user_profiles_redis:
                                    await RedisUserProfilesByRoomS.srem(redis, (room_id, current_id), r)
                                await RedisUserProfilesByRoomS.sadd(redis, (room_id, current_id), *[
                                    RedisUserProfilesByRoomS.schema(
                                        id=p.user_profile.id,
                                        nickname=p.user_profile.get_nickname_by_other(current_id),
                                        files=await redis_handler.generate_presigned_files(
                                            UserProfileImage, p.user_profile.images)
                                    ) for p in _room_user_mapping])

                        add_profile_ids: Set[int] = set(target_user_profile_ids)
                        profile_ids: Set[int] = add_profile_ids - current_profile_ids
                        if not profile_ids:
                            continue
                        profiles = await crud_user_profile.list(
                            conditions=(
                                UserProfile.id.in_(profile_ids), UserProfile.is_active == 1),
                            options=[
                                selectinload(UserProfile.images),
                                selectinload(UserProfile.followers)
                            ]
                        )
                        # DB 업데이트
                        new_room_name = _room_user_mapping[0].room.name + ', '.join([p.nickname for p in profiles])
                        _room_user_mapping[0].room.name = new_room_name
                        await crud_room_user_mapping.bulk_create([
                            dict(
                                room_id=room_id,
                                user_profile_id=profile_id,
                                room_name=new_room_name
                            ) for profile_id in profile_ids
                        ])
                        await session.commit()
                        # Redis 업데이트
                        _user_profiles = [m.user_profile for m in _room_user_mapping] + profiles
                        for target_profile in _user_profiles:
                            # 방에 있는 유저 정보들 업데이트
                            await RedisUserProfilesByRoomS.sadd(redis, (room_id, target_profile.id), *[
                                RedisUserProfilesByRoomS.schema(
                                    id=p.id,
                                    nickname=p.get_nickname_by_other(target_profile.id),
                                    files=await redis_handler.generate_presigned_files(
                                        UserProfileImage, p.images)
                                ) for p in profiles if p.id in profile_ids
                            ])
                            # 유저의 해당 방 정보 업데이트
                            _rooms_redis: List[RedisChatRoomByUserProfileS] = \
                                await RedisChatRoomsByUserProfileS.smembers(redis, target_profile.id)
                            _room_redis: RedisChatRoomByUserProfileS = next((
                                _r for _r in _rooms_redis if _r.id == room_id), None)
                            if _room_redis:
                                await RedisChatRoomsByUserProfileS.srem(redis, target_profile.id, _room_redis)
                                _room_redis.name = new_room_name
                                await RedisChatRoomsByUserProfileS.sadd(redis, target_profile.id, _room_redis)
                            else:
                                await RedisChatRoomsByUserProfileS.sadd(
                                    redis, target_profile.id, RedisChatRoomsByUserProfileS.schema(
                                        id=room_id, name=new_room_name,
                                        user_profile_files=await redis_handler.generate_presigned_files(
                                            UserProfileImage,
                                            [p for p in target_profile.images if target_profile.is_default]),
                                        unread_msg_cnt=0))
                        # 대화방 초대 메시지 전송
                        if len(profile_ids) > 1:
                            target_msg = '님과 '.join([p.nickname for p in profiles])
                        else:
                            target_msg = profiles[0].nickname
                        response_s = ChatSendFormS(
                            type=request_s.type,
                            data=ChatSendDataS(
                                text=f"{_user_profile_redis.nickname}님이 {target_msg}님을 초대했습니다.",
                                timestamp=request_s.data.timestamp))
                    await pub.publish(f"chat:{room_id}", response_s.json())
                except WebSocketDisconnect as exc:
                    raise exc
                except Exception as exc:
                    logger.error(get_log_error(exc))
        except WebSocketDisconnect as exc:
            now = datetime.now().astimezone()
            if exc.code == status.WS_1000_NORMAL_CLOSURE:
                try:
                    for s in await RedisUserProfilesByRoomS.smembers(redis, (room_id, user_profile_id)):
                        await RedisUserProfilesByRoomS.srem(redis, (room_id, user_profile_id), s)
                    for s in await RedisChatRoomsByUserProfileS.smembers(redis, user_profile_id):
                        if s.id == room_id:
                            await RedisChatRoomsByUserProfileS.srem(redis, user_profile_id, s)
                    delete_conditions = (
                        ChatRoomUserAssociation.room_id == room_id,
                        ChatRoomUserAssociation.user_profile_id == user_profile_id)
                    try:
                        room_user_mapping_db: ChatRoomUserAssociation = await crud_room_user_mapping.get(
                            conditions=delete_conditions,
                            options=[
                                joinedload(ChatRoomUserAssociation.room)
                                .selectinload(ChatRoom.user_profiles)
                            ]
                        )
                    except HTTPException:
                        pass
                    else:
                        # 유저와 대화방 연결 해제
                        _room_db = room_user_mapping_db.room
                        await crud_room_user_mapping.delete(conditions=delete_conditions)
                        await session.flush()
                        if not _room_db.user_profiles:
                            await crud_room.update(values={'is_active': False}, conditions=(
                                ChatRoom.id == _room_db.id,
                                ChatRoom.is_active == 1))
                        await session.commit()
                        # 유저 연결 해제 메시지 전송
                        response_s = ChatSendFormS(
                            type=ChatType.MESSAGE,
                            data=ChatSendDataS(
                                text=f"{user_profile_redis.nickname}님이 나갔습니다.",
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
