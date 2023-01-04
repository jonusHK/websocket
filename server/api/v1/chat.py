import asyncio
import base64
import json
import logging
from copy import deepcopy
from datetime import datetime
from io import BytesIO
from typing import List, Set, Dict, Any

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
from websockets.exceptions import ConnectionClosedOK

from server.api import ExceptionHandlerRoute, templates
from server.api.common import AuthValidator, RedisHandler
from server.core.authentications import cookie, RoleChecker
from server.core.enums import UserType, ChatType, ChatRoomType
from server.core.exceptions import ExceptionHandler
from server.core.externals.redis import AioRedis
from server.core.externals.redis.schemas import RedisUserProfilesByRoomS, \
    RedisChatHistoriesByRoomS, RedisUserProfileByRoomS, RedisChatHistoryByRoomS, \
    RedisChatRoomsByUserProfileS, RedisChatRoomByUserProfileS, RedisChatHistoryFileS, RedisFollowingsByUserProfileS, \
    RedisFollowingByUserProfileS, RedisUserImageFileS, RedisChatRoomsInfoS, RedisChatRoomInfoS
from server.crud.service import ChatRoomUserAssociationCRUD, ChatRoomCRUD, ChatHistoryCRUD, \
    ChatHistoryUserAssociationCRUD
from server.crud.user import UserProfileCRUD
from server.db.databases import get_async_session, settings, async_session
from server.models import User, UserProfile, ChatRoom, ChatRoomUserAssociation, ChatHistory, \
    ChatHistoryUserAssociation, ChatHistoryFile, UserProfileImage, UserRelationship
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


@router.get("/followings", response_class=HTMLResponse)
def followings(request: Request):
    return templates.TemplateResponse("followings.html", {"request": request})


@router.websocket("/rooms/{user_profile_id}")
async def chat_room(
    websocket: WebSocket,
    user_profile_id: int
):
    """
    대화 방 목록 조회
    """
    def get_log_error(exc: Exception):
        return f"Chat Room Error - user_profile_id: {user_profile_id}, " \
               f"reason: {ExceptionHandler(exc).error}"

    redis: Redis = AioRedis().redis
    redis_handler = RedisHandler(redis)

    async with async_session() as session:
        user: User = await AuthValidator(session).get_user_by_websocket(websocket)
        if not next((p for p in user.profiles if p.id == user_profile_id), None):
            raise WebSocketDisconnect(code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA)

    await websocket.accept()

    async def producer_handler(pub: Redis, ws: WebSocket):
        while True:
            async with async_session() as session:
                crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)
                try:
                    rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = \
                        await redis_handler.get_rooms_by_user_profile(
                            user_profile_id=user_profile_id, crud=crud_room_user_mapping, sync=True, reverse=True
                        )

                    result = []
                    if rooms_by_profile_redis:
                        room_ids: List[int] = [r.id for r in rooms_by_profile_redis]
                        rooms: List[RedisChatRoomInfoS] = await RedisChatRoomsInfoS.smembers(redis, None)
                        rooms = [r for r in rooms if r.id in room_ids] if rooms else []
                        for room_by_profile_redis in rooms_by_profile_redis:
                            obj: Dict[str, Any] = jsonable_encoder(room_by_profile_redis)
                            room: RedisChatRoomInfoS = next((
                                r for r in rooms if r.id == room_by_profile_redis.id), None)
                            chat_histories: List[RedisChatHistoryByRoomS] = \
                                await RedisChatHistoriesByRoomS.zrevrange(redis, room_by_profile_redis.id, 0, 1)
                            obj.update({
                                'user_cnt': room.user_cnt if room else None,
                                'type': room.type if room else None,
                                'user_profile_files': room.user_profile_files if room else None,
                                # 마지막 대화 내역 추출
                                'last_chat_history': jsonable_encoder(chat_histories[0]) if chat_histories else None
                            })
                            result.append(obj)
                    await pub.publish(f"pubsub:user:{user_profile_id}:chat_room", json.dumps(result))
                    await websocket.send_json(result)
                except (WebSocketDisconnect, ConnectionClosedOK) as e:
                    logger.exception(e)
                    raise e
                except Exception as e:
                    logger.exception(e)

    async def consumer_handler(psub: PubSub, ws: WebSocket):
        try:
            async with psub as p:
                await p.subscribe(f"pubsub:user:{user_profile_id}:chat_room")
                try:
                    while True:
                        message: dict = await p.get_message(ignore_subscribe_messages=True)
                        if message:
                            await ws.send_json(json.loads(message.get('data')))
                except (asyncio.CancelledError, ConnectionClosedOK) as exc:
                    logger.error(get_log_error(exc))
                    await p.unsubscribe()
                    raise exc
                except Exception as exc:
                    logger.error(get_log_error(exc))
        except (asyncio.CancelledError, ConnectionClosedOK):
            await psub.close()

    await redis_handler.handle_pubsub(websocket, producer_handler, consumer_handler, logger)


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
    now = datetime.now().astimezone()
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
    target_profiles: List[UserProfile] = await crud_user_profile.list(
        conditions=(
            UserProfile.id.in_(data.target_profile_ids),
            UserProfile.is_active == 1))
    if len(data.target_profile_ids) != len(target_profiles):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Not exists all for target profile ids.")

    mapping_profile_ids: List[int] = data.target_profile_ids + [data.user_profile_id]

    # 1:1 방 생성 시, 기존 방 있다면 리턴
    if data.type == ChatRoomType.ONE_TO_ONE:
        _rooms: List[ChatRoom] = await crud_room_user_mapping.list(
            join=[(ChatRoom, ChatRoomUserAssociation.room_id == ChatRoom.id)],
            with_only_columns=(
                ChatRoom,
                func.count(ChatRoomUserAssociation.user_profile_id).label('profile_cnt')),
            conditions=(
                ChatRoom.is_active == 1,
                ChatRoomUserAssociation.user_profile_id.in_(mapping_profile_ids)),
            group_by=(ChatRoomUserAssociation.room_id,),
            having=(func.count(ChatRoomUserAssociation.user_profile_id) == len(mapping_profile_ids)))
        if _rooms:
            _room = _rooms[-1]
            for profile_id in mapping_profile_ids:
                await redis_handler.get_room_by_user_profile(_room.id, profile_id, crud_room, sync=True)
                await redis_handler.get_user_profiles_in_room(_room.id, profile_id, crud_room_user_mapping, sync=True)
            return ChatRoomS.from_orm(_room)

    # 채팅방 생성 이후 유저와 채팅방 연결
    room: ChatRoom = await crud_room.create(type=data.type)
    await session.flush()
    room = await crud_room.get(
        conditions=(ChatRoom.id == room.id,),
        options=[selectinload(ChatRoom.user_profiles)])

    mapping_profiles: List[UserProfile] = await crud_user_profile.list(
        conditions=(
            UserProfile.id.in_(mapping_profile_ids),
            UserProfile.is_active == 1),
        options=[selectinload(UserProfile.followers)]
    )

    for p in mapping_profiles:
        room.user_profiles.append(
            ChatRoomUserAssociation(room_id=room.id, user_profile_id=p.id))
    await session.commit()

    # Redis 데이터 업데이트
    room: ChatRoom = await crud_room.get(
        conditions=(ChatRoom.id == room.id,),
        options=[
            selectinload(ChatRoom.user_profiles)
            .joinedload(ChatRoomUserAssociation.user_profile)
            .selectinload(UserProfile.images),
            selectinload(ChatRoom.user_profiles)
            .joinedload(ChatRoomUserAssociation.user_profile)
            .selectinload(UserProfile.followers)
        ])

    default_profile_images: List[RedisUserImageFileS] = await redis_handler.generate_user_profile_images(
        [m.user_profile for m in room.user_profiles], only_default=True)
    user_profile_ids = []
    for m in room.user_profiles:
        user_profile_ids.append(m.user_profile_id)
        await RedisChatRoomsByUserProfileS.zadd(redis, m.user_profile_id, RedisChatRoomsByUserProfileS.schema(
            id=room.id,
            unread_msg_cnt=0,
            timestamp=now.timestamp()
        ))
        await RedisUserProfilesByRoomS.sadd(
            redis, (room.id, m.user_profile_id), *[
                RedisUserProfilesByRoomS.schema(
                    id=n.user_profile_id,
                    identity_id=n.user_profile.identity_id,
                    nickname=n.user_profile.get_nickname_by_other(m.user_profile_id),
                    files=[im for im in default_profile_images if im.user_profile_id == n.user_profile_id]
                ) for n in room.user_profiles
            ])

    await RedisChatRoomsInfoS.sadd(redis, room.id, RedisChatRoomsInfoS.schema(
        id=room.id,
        type=room.type.name.lower(),
        user_profile_ids=user_profile_ids,
        user_profile_files=default_profile_images,
        user_cnt=len(user_profile_ids)))

    return ChatRoomS.from_orm(room)


@router.websocket("/conversation/{user_profile_id}/{room_id}")
async def chat(
    websocket: WebSocket,
    user_profile_id: int,
    room_id: int
):
    """
    대화 방 입장 및 실시간 채팅
    """
    def get_log_error(exc: Exception):
        return f"Chat Error - room_id: {room_id}, user_profile_id: {user_profile_id}, " \
               f"reason: {ExceptionHandler(exc).error}"

    redis: Redis = AioRedis().redis
    redis_handler = RedisHandler(redis)

    async with async_session() as session:
        user: User = await AuthValidator(session).get_user_by_websocket(websocket)
        if not next((p for p in user.profiles if p.id == user_profile_id), None):
            raise WebSocketDisconnect(code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA, reason='Unauthorized user.')

        try:
            # 방 데이터 추출
            try:
                await redis_handler.get_room(room_id, ChatRoomCRUD(session), sync=True)
            except Exception as e:
                raise WebSocketDisconnect(
                    code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                    reason=f'Not exist room. {e}'
                )

            # 유저가 속한 방 데이터 추출
            try:
                await redis_handler.get_room_by_user_profile(
                    room_id, user_profile_id, ChatRoomCRUD(session), sync=True
                )
            except Exception as e:
                raise WebSocketDisconnect(
                    code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                    reason=f'Not exist room by user. {e}'
                )

            # 방에 속한 유저들 프로필 데이터 추출
            try:
                user_profiles_redis: List[RedisUserProfileByRoomS] = await redis_handler.get_user_profiles_in_room(
                    room_id, user_profile_id, ChatRoomUserAssociationCRUD(session), sync=True
                )
            except Exception as e:
                raise WebSocketDisconnect(
                    code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                    reason=f'Failed to get user profiles in the room. {e}'
                )
            else:
                # 방에 해당 유저 존재 여부 확인
                if not next((p for p in user_profiles_redis if p.id == user_profile_id), None):
                    raise WebSocketDisconnect(
                        code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                        reason='Not exist the user in the room.'
                    )

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

                async with async_session() as session:
                    crud_room = ChatRoomCRUD(session)
                    crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)
                    crud_chat_history = ChatHistoryCRUD(session)
                    crud_history_user_mapping = ChatHistoryUserAssociationCRUD(session)
                    crud_user_profile = UserProfileCRUD(session)

                    try:
                        # 방 데이터 추출
                        try:
                            room_redis: RedisChatRoomInfoS = await redis_handler.get_room(room_id, crud_room, sync=True)
                        except Exception as e:
                            raise WebSocketDisconnect(
                                code=status.WS_1000_NORMAL_CLOSURE,
                                reason=f'Failed to get room. {e}'
                            )
                        # 유저에 연결된 방 데이터 추출
                        try:
                            room_by_profile_redis: RedisChatRoomByUserProfileS = \
                                await redis_handler.get_room_by_user_profile(
                                    room_id, user_profile_id, crud_room, sync=True
                                )
                        except Exception as e:
                            raise WebSocketDisconnect(
                                code=status.WS_1000_NORMAL_CLOSURE,
                                reason=f'Failed to get room for user profile. {e}'
                            )
                        # 방에 속한 유저들 프로필 데이터 추출
                        try:
                            user_profiles_redis: List[RedisUserProfileByRoomS] = \
                                await redis_handler.get_user_profiles_in_room(
                                    room_id, user_profile_id, crud_room_user_mapping, sync=True
                                )
                        except Exception as e:
                            raise WebSocketDisconnect(
                                code=status.WS_1000_NORMAL_CLOSURE,
                                reason=f'Failed to get user profiles in the room. {e}'
                            )

                        # 방에 해당 유저 존재 여부 확인
                        user_profile_redis: RedisUserProfileByRoomS = next(
                            (p for p in user_profiles_redis if p.id == user_profile_id), None
                        )
                        if not user_profile_redis:
                            raise WebSocketDisconnect(
                                code=status.WS_1000_NORMAL_CLOSURE,
                                reason='Left the chat room.'
                            )

                        # 요청 데이터 확보
                        request_s = ChatReceiveFormS(**data)

                        # 업데이트 요청
                        if request_s.type == ChatType.UPDATE:
                            if not request_s.data.history_ids:
                                raise WebSocketDisconnect(
                                    code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                    reason='Not exists chat history ids.'
                                )
                            _chat_histories_redis: List[RedisChatHistoryByRoomS] = \
                                await RedisChatHistoriesByRoomS.zrevrange(redis, room_id)
                            if not _chat_histories_redis:
                                raise WebSocketDisconnect(
                                    code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                    reason='Not exists chat histories in the room.'
                                )
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
                                    conditions=(ChatHistory.id.in_(_update_target_db),)
                                )
                                await session.commit()
                            response_s = ChatSendFormS(
                                type=request_s.type,
                                data=ChatSendDataS(
                                    history_ids=request_s.data.history_ids,
                                    is_active=request_s.data.is_active
                                )
                            )
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
                                is_active=True
                            ))
                            # 각 유저 별 해당 방의 unread_msg_cnt 업데이트
                            for p in user_profiles_redis:
                                _unread_msg_cnt = 1
                                _room_by_profile_redis: RedisChatRoomByUserProfileS = \
                                    await redis_handler.get_room_by_user_profile(room_id, p.id, crud_room, sync=True)
                                if _room_by_profile_redis:
                                    await RedisChatRoomsByUserProfileS.zrem(redis, p.id, _room_by_profile_redis)
                                    _unread_msg_cnt += _room_by_profile_redis.unread_msg_cnt
                                    await RedisChatRoomsByUserProfileS.zadd(
                                        redis, p.id, RedisChatRoomsByUserProfileS.schema(
                                            id=_room_by_profile_redis.id,
                                            name=_room_by_profile_redis.name,
                                            unread_msg_cnt=_unread_msg_cnt,
                                            timestamp=request_s.data.timestamp
                                        ))
                            response_s = ChatSendFormS(
                                type=request_s.type,
                                data=ChatSendDataS(
                                    user_profile_id=user_profile_id,
                                    nickname=user_profile_redis.nickname,
                                    timestamp=request_s.data.timestamp,
                                    text=request_s.data.text,
                                    is_active=request_s.data.is_active
                                ))
                        # 파일 업로드 요청
                        elif request_s.type == ChatType.FILE:
                            chat_history_db: ChatHistory = await crud_chat_history.create(
                                room_id=room_id, user_profile_id=user_profile_id
                            )
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
                                is_active=chat_history_db.is_active
                            ))
                            response_s = ChatSendFormS(
                                type=request_s.type,
                                data=ChatSendDataS(
                                    user_profile_id=user_profile_id,
                                    nickname=user_profile_redis.nickname,
                                    files=files_s,
                                    timestamp=request_s.data.timestamp,
                                    is_active=chat_history_db.is_active
                                ))
                        # 대화 내용 조회
                        elif request_s.type == ChatType.LOOKUP:
                            if not request_s.data.offset or not request_s.data.limit:
                                raise WebSocketDisconnect(
                                    code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                    reason='Not exists offset or limit for page.'
                                )

                            # 해당 방의 unread_msg_cnt = 0 설정 (채팅방 접속 시, 0으로 초기화)
                            await RedisChatRoomsByUserProfileS.zrem(redis, user_profile_id, room_by_profile_redis)
                            room_by_profile_redis.unread_msg_cnt = 0
                            await RedisChatRoomsByUserProfileS.zadd(redis, user_profile_id, room_by_profile_redis)
                            # Redis 대화 내용 조회
                            chat_histories_redis: List[RedisChatHistoryByRoomS] = \
                                await RedisChatHistoriesByRoomS.zrevrange(
                                    redis, room_id,
                                    start=request_s.data.offset + 1,
                                    end=request_s.data.offset + request_s.data.limit
                                )
                            # Redis 데이터 없는 경우 DB 조회
                            lack_cnt: int = request_s.data.limit - len(chat_histories_redis)
                            if lack_cnt > 0:
                                if chat_histories_redis:
                                    next_offset: int = request_s.data.offset + len(chat_histories_redis) + 1
                                else:
                                    next_offset: int = request_s.data.offset
                                chat_histories_db: List[ChatHistory] = await crud_chat_history.list(
                                    conditions=(
                                        ChatHistory.room_id == room_id,
                                        ChatHistory.user_profile_id == user_profile_id
                                    ),
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
                                            m = next((
                                                m for m in h.user_profile_mapping
                                                if m.user_profile_id == user_profile_id), None)
                                            if m:
                                                if not m.is_read:
                                                    _update_target_db.append(m)
                                            else:
                                                _create_target_db.append(h)
                                    if _create_target_db:
                                        await crud_history_user_mapping.bulk_create([
                                            dict(
                                                history_id=h.id,
                                                user_profile_id=user_profile_id
                                            ) for h in _create_target_db
                                        ])
                                        await session.commit()
                                    if _update_target_db:
                                        await crud_history_user_mapping.bulk_update([
                                            dict(id=m.id, is_read=True) for m in _update_target_db
                                        ])
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
                                        redis, (room_id, user_profile_id)
                                    ),
                                    timestamp=request_s.data.timestamp
                                ))
                        # 유저 초대
                        elif request_s.type == ChatType.INVITE:
                            target_user_profile_ids: List[int] = request_s.data.target_user_profile_ids
                            if not target_user_profile_ids:
                                raise WebSocketDisconnect(
                                    code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA,
                                    reason='Not exists user profile ids for invite.'
                                )
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
                            # 방에 속한 유저 -> Redis, DB 동기화
                            current_profiles: List[UserProfile] = [m.user_profile for m in _room_user_mapping]
                            current_profile_images_redis: List[RedisUserImageFileS] = \
                                await redis_handler.generate_user_profile_images(current_profiles, only_default=True)
                            current_profile_ids: Set[int] = {p.id for p in current_profiles}
                            for current_id in current_profile_ids:
                                _user_profiles_redis: List[RedisUserProfileByRoomS] = \
                                    await RedisUserProfilesByRoomS.smembers(redis, (room_id, current_id))
                                if len(_user_profiles_redis) != len(_room_user_mapping):
                                    for r in _user_profiles_redis:
                                        await RedisUserProfilesByRoomS.srem(redis, (room_id, current_id), r)
                                    await RedisUserProfilesByRoomS.sadd(redis, (room_id, current_id), *[
                                        RedisUserProfilesByRoomS.schema(
                                            id=m.user_profile.id,
                                            identity_id=m.user_profile.identity_id,
                                            nickname=m.user_profile.get_nickname_by_other(current_id),
                                            files=[
                                                im for im in current_profile_images_redis
                                                if im.user_profile_id == m.user_profile_id]
                                        ) for m in _room_user_mapping
                                    ])

                            add_profile_ids: Set[int] = set(target_user_profile_ids)
                            profile_ids: Set[int] = add_profile_ids - current_profile_ids
                            if not profile_ids:
                                continue
                            profiles: List[UserProfile] = await crud_user_profile.list(
                                conditions=(
                                    UserProfile.id.in_(profile_ids),
                                    UserProfile.is_active == 1),
                                options=[
                                    selectinload(UserProfile.images),
                                    selectinload(UserProfile.followers)
                                ]
                            )
                            # 초대 받은 유저에 대해 DB 방 연동
                            await crud_room_user_mapping.bulk_create([
                                dict(room_id=room_id, user_profile_id=p.id) for p in profiles
                            ])
                            await session.commit()

                            # 초대 받은 유저에 대해 Redis 업데이트
                            total_profiles: List[UserProfile] = current_profiles + profiles
                            profile_images_redis: List[RedisUserImageFileS] = \
                                await redis_handler.generate_user_profile_images(profiles, only_default=True)
                            total_profile_images_redis: List[RedisUserImageFileS] = \
                                current_profile_images_redis + profile_images_redis

                            # 방 정보 업데이트
                            await RedisChatRoomsInfoS.srem(redis, None, room_redis)
                            room_redis.user_cnt = len(total_profiles)
                            room_redis.user_profile_ids = [p.id for p in total_profiles]
                            room_redis.user_profile_files = total_profile_images_redis
                            await RedisChatRoomsInfoS.sadd(redis, None, room_redis)

                            for target_profile in total_profiles:
                                # 각 방에 있는 유저 기준으로 데이터 업데이트
                                await RedisUserProfilesByRoomS.sadd(redis, (room_id, target_profile.id), *[
                                    RedisUserProfilesByRoomS.schema(
                                        id=p.id,
                                        identity_id=p.identity_id,
                                        nickname=p.get_nickname_by_other(target_profile.id),
                                        files=[im for im in total_profile_images_redis if im.user_profile_id == p.id]
                                    ) for p in (total_profiles if target_profile in profiles else profiles)
                                ])
                                # 각 방에 있는 유저의 방 정보 업데이트
                                _room_by_profile_redis = await redis_handler.get_room_by_user_profile(
                                    room_id, target_profile.id, crud_room, sync=True)
                                if _room_by_profile_redis:
                                    await RedisChatRoomsByUserProfileS.zrem(
                                        redis, target_profile.id, _room_by_profile_redis
                                    )
                                    _room_by_profile_redis.timestamp = request_s.data.timestamp
                                    await RedisChatRoomsByUserProfileS.zadd(
                                        redis, target_profile.id, _room_by_profile_redis
                                    )
                                else:
                                    await RedisChatRoomsByUserProfileS.zadd(
                                        redis, target_profile.id, RedisChatRoomsByUserProfileS.schema(
                                            id=room_id, unread_msg_cnt=0, timestamp=request_s.data.timestamp
                                        )
                                    )
                            # 대화방 초대 메시지 전송
                            if len(profiles) > 1:
                                target_msg = '님과 '.join([p.nickname for p in profiles])
                            else:
                                target_msg = profiles[0].nickname
                            response_s = ChatSendFormS(
                                type=request_s.type,
                                data=ChatSendDataS(
                                    text=f"{user_profile_redis.nickname}님이 {target_msg}님을 초대했습니다.",
                                    timestamp=request_s.data.timestamp))
                        # 연결 종료
                        else:
                            try:
                                room_user_mappings_db: List[ChatRoomUserAssociation] = await crud_room_user_mapping.list(
                                    conditions=(ChatRoomUserAssociation.room_id == room_id,),
                                    options=[
                                        joinedload(ChatRoomUserAssociation.room)
                                        .selectinload(ChatRoom.user_profiles),
                                        joinedload(ChatRoomUserAssociation.user_profile)
                                    ])
                            except HTTPException:
                                pass
                            else:
                                room_db: ChatRoom | None = None
                                # 유저와 대화방 연결 해제
                                room_user_mapping_db: ChatRoomUserAssociation = next((
                                    m for m in room_user_mappings_db
                                    if m.user_profile_id == user_profile_id), None
                                )
                                if room_user_mapping_db:
                                    room_db = room_user_mapping_db.room
                                    # 방에 아무도 연동되어 있지 않으면, 비활성화 처리
                                    if len(room_user_mappings_db) == 1:
                                        room_db.is_active = False
                                    await crud_room_user_mapping.delete(conditions=(
                                        ChatRoomUserAssociation.room_id == room_id,
                                        ChatRoomUserAssociation.user_profile_id == user_profile_id))
                                    await session.commit()
                                    await session.refresh()

                                await RedisUserProfilesByRoomS.srem(redis, (room_id, user_profile_id), user_profile_redis)
                                await RedisChatRoomsByUserProfileS.zrem(redis, user_profile_id, room_by_profile_redis)
                                await RedisChatRoomsInfoS.srem(redis, None, room_redis)
                                room_redis.user_cnt -= 1
                                room_redis.user_profile_ids = [
                                    i for i in room_redis.user_profile_ids if i != user_profile_id
                                ]
                                room_redis.user_profile_files = [
                                    f for f in room_redis.user_profile_files if f.user_profile_id != user_profile_id
                                ]
                                if room_db:
                                    room_redis.is_active = room_db.is_active
                                await RedisChatRoomsInfoS.sadd(redis, None, room_redis)

                            response_s = ChatSendFormS(
                                type=ChatType.MESSAGE,
                                data=ChatSendDataS(
                                    text=f"{user_profile_redis.nickname}님이 나갔습니다.",
                                    timestamp=request_s.data.timestamp
                                ))
                        await pub.publish(f"pubsub:room:{room_id}:chat", response_s.json())
                    except WebSocketDisconnect as exc:
                        raise exc
                    except Exception as exc:
                        logger.error(get_log_error(exc))
        except WebSocketDisconnect as exc:
            logger.exception(get_log_error(exc))
            raise exc

    async def consumer_handler(psub: PubSub, ws: WebSocket):
        try:
            async with psub as p:
                await p.subscribe(f"pubsub:room:{room_id}:chat")
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

    await redis_handler.handle_pubsub(websocket, producer_handler, consumer_handler, logger)


@router.websocket('/followings/{user_profile_id}')
async def chat_followings(websocket: WebSocket, user_profile_id: int):
    """
    친구 목록 조회
    """
    def get_log_error(exc: Exception):
        return f"Followings Error - user_profile_id: {user_profile_id}, " \
               f"reason: {ExceptionHandler(exc).error}"

    async with async_session() as session:
        user: User = await AuthValidator(session).get_user_by_websocket(websocket)
        user_profile: UserProfile = next((p for p in user.profiles if p.id == user_profile_id and p.is_active), None)
        if not user_profile:
            raise WebSocketDisconnect(code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA, reason='Unauthorized user.')

        redis: Redis = AioRedis().redis
        redis_handler = RedisHandler(redis)

        await websocket.accept()

    async def producer_handler(pub: Redis, ws: WebSocket):
        try:
            while True:
                async with async_session() as session:
                    crud_user_profile = UserProfileCRUD(session)
                    while True:
                        followings: List[RedisFollowingByUserProfileS] = \
                            await RedisFollowingsByUserProfileS.smembers(redis, user_profile_id)
                        if followings:
                            break
                        if not followings:
                            user_profile: UserProfile = await crud_user_profile.get(
                                conditions=(
                                    UserProfile.id == user_profile_id,
                                    UserProfile.is_active == 1),
                                options=[
                                    selectinload(UserProfile.followings).
                                    joinedload(UserRelationship.other_profile).
                                    selectinload(UserProfile.images),
                                    selectinload(UserProfile.followings).
                                    joinedload(UserRelationship.other_profile).
                                    selectinload(UserProfile.followers)
                                ])
                            await RedisFollowingsByUserProfileS.sadd(redis, user_profile_id, *[
                                RedisFollowingsByUserProfileS.schema(
                                    id=f.other_profile_id,
                                    identity_id=f.other_profile.identity_id,
                                    nickname=f.other_profile.get_nickname_by_other(user_profile_id),
                                    type=f.type.name.lower(),
                                    favorites=f.favorites,
                                    is_hidden=f.is_hidden,
                                    is_forbidden=f.is_forbidden,
                                    files=await redis_handler.generate_presigned_files(
                                        UserProfileImage, [i for i in f.other_profile.images if i.is_default])
                                ) for f in user_profile.followings if not f.is_hidden and not f.is_forbidden
                            ])
                await pub.publish(f'pubsub:user:{user_profile_id}:following', json.dumps(jsonable_encoder(followings)))
        except WebSocketDisconnect as e:
            logger.exception(e)
            raise e
        except Exception as e:
            logger.exception(e)

    async def consumer_handler(psub: PubSub, ws: WebSocket):
        try:
            async with psub as p:
                await p.subscribe(f"pubsub:user:{user_profile_id}:following")
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

    await redis_handler.handle_pubsub(websocket, producer_handler, consumer_handler, logger)
