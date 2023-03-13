import asyncio
import base64
import json
import logging
import uuid
from copy import deepcopy
from datetime import datetime
from io import BytesIO
from itertools import groupby
from typing import List, Set, Dict, Any, Optional, Tuple

from aioredis import Redis
from aioredis.client import PubSub
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette import status
from starlette.responses import HTMLResponse
from websockets.exceptions import WebSocketException

from server.api import ExceptionHandlerRoute, templates
from server.api.common import AuthValidator, RedisHandler, WebSocketHandler
from server.core.authentications import cookie, RoleChecker
from server.core.enums import UserType, ChatType, ChatHistoryType, ResponseCode
from server.core.exceptions import ExceptionHandler
from server.core.externals.redis.schemas import (
    RedisUserProfilesByRoomS,
    RedisChatHistoriesByRoomS, RedisUserProfileByRoomS, RedisChatHistoryByRoomS,
    RedisChatRoomsByUserProfileS, RedisChatHistoryFileS, RedisFollowingsByUserProfileS,
    RedisFollowingByUserProfileS, RedisUserImageFileS, RedisChatRoomByUserProfileS, RedisChatHistoryPatchS,
    RedisInfoByRoomS, RedisChatRoomInfoS
)
from server.core.utils import async_iter
from server.crud.service import (
    ChatRoomUserAssociationCRUD, ChatRoomCRUD, ChatHistoryCRUD, ChatHistoryUserAssociationCRUD
)
from server.crud.user import UserProfileCRUD
from server.db.databases import get_async_session, settings, async_session
from server.models import (
    User, UserProfile, ChatRoom, ChatRoomUserAssociation, ChatHistory,
    ChatHistoryUserAssociation, ChatHistoryFile, UserRelationship, UserProfileImage
)
from server.schemas.base import WebSocketFileS
from server.schemas.chat import ChatSendFormS, ChatSendDataS, ChatReceiveFormS, ChatRoomCreateParamS
from server.schemas.service import ChatRoomS

router = APIRouter(route_class=ExceptionHandlerRoute)

logger = logging.getLogger('chat')


@router.get('', response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})


@router.get('/rooms', response_class=HTMLResponse)
def rooms(request: Request):
    return templates.TemplateResponse('rooms.html', {'request': request})


@router.get('/followings', response_class=HTMLResponse)
def followings(request: Request):
    return templates.TemplateResponse('followings.html', {'request': request})


@router.get('/room/{user_profile_id}/{room_id}')
async def chat_room_by_profile(
    room_id: int,
    user_profile_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    redis_hdr = RedisHandler()
    try:
        room_by_profile_redis, _ = await redis_hdr.get_room_by_user_profile(
            room_id, user_profile_id,
            crud=ChatRoomUserAssociationCRUD(session),
            sync=True, raise_exception=True
        )
        profiles_by_room_redis: List[RedisUserProfileByRoomS] = await RedisUserProfilesByRoomS.smembers(
            await redis_hdr.redis, (room_id, user_profile_id)
        )
        room_name: str | None = (
            room_by_profile_redis.name
            or await redis_hdr.generate_default_room_name(
                room_id, user_profile_id, profiles_by_room_redis
            )
        )
    finally:
        await redis_hdr.close()

    obj: Dict[str, Any] = jsonable_encoder(room_by_profile_redis)
    obj.update(jsonable_encoder({
        'name': room_name,
        'user_profiles': profiles_by_room_redis,
    }))
    return obj


@router.websocket('/rooms/{user_profile_id}')
async def chat_rooms(
    websocket: WebSocket,
    user_profile_id: int
):
    """
    대화 방 목록 조회
    """
    def get_log_error(exc: BaseException):
        return (
            f'Chat Room Error - user_profile_id: {user_profile_id}, '
            f'reason: {ExceptionHandler(exc).error}'
        )

    ws_handler = WebSocketHandler(websocket)
    await ws_handler.accept()
    async with async_session() as session:
        try:
            user: User = await AuthValidator(session).get_user_by_websocket(websocket)
            if not next((p for p in user.profiles if p.id == user_profile_id), None):
                raise WebSocketDisconnect(status.WS_1008_POLICY_VIOLATION)
        except:
            code, reason = status.WS_1008_POLICY_VIOLATION, ResponseCode.UNAUTHORIZED.value
            await ws_handler.close(code=code, reason=reason)
            raise WebSocketDisconnect(code=code, reason=reason)

    async def producer_handler():
        while True:
            async with async_session() as session:
                try:
                    crud_room = ChatRoomCRUD(session)
                    crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)

                    duplicated_rooms_by_profile_redis, _ = await redis_hdr.get_rooms_by_user_profile(
                        user_profile_id=user_profile_id, crud=crud_room_user_mapping,
                        lock=False, reverse=True
                    )
                    result = []
                    if duplicated_rooms_by_profile_redis:
                        duplicated_rooms_by_profile_redis.sort(key=lambda x: (x.id, -x.timestamp))
                        rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = []
                        for key, items in groupby(duplicated_rooms_by_profile_redis, key=lambda x: x.id):
                            items = list(items)
                            rooms_by_profile_redis.append(items[0])

                        rooms_by_profile_redis.sort(key=lambda x: x.timestamp, reverse=True)
                        for room_by_profile_redis in rooms_by_profile_redis:
                            room, _ = await redis_hdr.get_room(
                                room_by_profile_redis.id, crud_room, sync=True, lock=False
                            )
                            if not room:
                                continue

                            profiles_by_room_redis: List[RedisUserProfileByRoomS] = (
                                await RedisUserProfilesByRoomS.smembers(
                                    await redis_hdr.redis, (room.id, user_profile_id)
                                )
                            )
                            room_name: str = (
                                room_by_profile_redis.name
                                or await redis_hdr.generate_default_room_name(
                                    room_by_profile_redis.id, user_profile_id, profiles_by_room_redis
                                )
                            )

                            chat_histories: List[RedisChatHistoryByRoomS] = (
                                await RedisChatHistoriesByRoomS.zrevrange(
                                    await redis_hdr.redis, room_by_profile_redis.id, 0, 1
                                )
                            )
                            last_chat_history = None
                            if chat_histories:
                                last_chat_history = chat_histories[0]

                            obj: Dict[str, Any] = jsonable_encoder(room_by_profile_redis)
                            obj.update(jsonable_encoder({
                                'name': room_name,
                                'type': room.type if room else None,
                                'user_profiles': profiles_by_room_redis,
                                'user_profile_files': room.user_profile_files if room else None,
                                'last_chat_history': last_chat_history,
                                'last_chat_timestamp': last_chat_history and last_chat_history.timestamp
                            }))
                            result.append(obj)
                    await ws_handler.send_json(result)
                except (WebSocketDisconnect, WebSocketException) as e:
                    await ws_handler.close(e=e)
                    if not ws_handler.self_disconnected(e):
                        logger.exception(get_log_error(e))
                    raise e
                except Exception as e:
                    if e.__class__.__name__ not in raised_errors:
                        logger.exception(get_log_error(e))
                        raised_errors.add(e.__class__.__name__)

    async def consumer_handler():
        while True:
            data = await ws_handler.receive_json()
            if data:
                request_s = ChatReceiveFormS(**data)
                if request_s.type == ChatType.PING:
                    await ws_handler.send_text('pong')

    raised_errors = set()
    redis_hdr = RedisHandler()
    try:
        done, pending = await asyncio.wait([
            producer_handler(), consumer_handler()
        ], return_when=asyncio.FIRST_COMPLETED)

        if pending:
            for task in pending:
                task.cancel()
    finally:
        await redis_hdr.close()


@router.post(
    '/rooms/create',
    dependencies=[Depends(cookie), Depends(RoleChecker([UserType.USER]))],
    response_model=ChatRoomS,
    status_code=status.HTTP_201_CREATED
)
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
            UserProfile.is_active == 1
        )
    )
    if len(data.target_profile_ids) != len(target_profiles):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail='Not exists all for target profile ids.')

    mapping_profile_ids: Set[int] = set(data.target_profile_ids + [data.user_profile_id])

    redis_hdr = RedisHandler()
    try:
        # 1:1 방 혹은 나와의 채팅방 생성 시, 기존 방 있다면 리턴
        if len(mapping_profile_ids) <= 2:
            active_rooms: List[ChatRoom] = await crud_room.list(
                conditions=(ChatRoom.is_active == 1,),
                options=[selectinload(ChatRoom.user_profiles).load_only('user_profile_id')],
                order_by=(ChatRoom.created.desc(),)
            )
            room: ChatRoom | None = None
            for r in active_rooms:
                if r.user_profiles:
                    profile_ids: Set[int] = {m.user_profile_id for m in r.user_profiles}
                    if (
                        len(profile_ids) == len(mapping_profile_ids)
                        and len(profile_ids - mapping_profile_ids) == 0
                    ):
                        room = r
                        break
            if room:
                async with await redis_hdr.pipeline() as pipe:
                    for profile_id in mapping_profile_ids:
                        _, pipe = await redis_hdr.get_room_by_user_profile(
                            room.id, profile_id, crud_room_user_mapping, pipe=pipe, sync=True
                        )
                        _, pipe = await redis_hdr.get_user_profiles_in_room(
                            room.id, profile_id, crud_room_user_mapping, pipe=pipe, sync=True
                        )
                    if pipe:
                        await pipe.execute()
                return ChatRoomS.from_orm(room)

        # 채팅방 생성 이후 유저와 채팅방 연결
        room: ChatRoom = await crud_room.create(type=data.type)
        await session.flush()
        room: ChatRoom = await crud_room.get(
            conditions=(ChatRoom.id == room.id,),
            options=[
                selectinload(ChatRoom.user_profiles)
                .joinedload(ChatRoomUserAssociation.user_profile)
                .selectinload(UserProfile.images),
                selectinload(ChatRoom.user_profiles)
                .joinedload(ChatRoomUserAssociation.user_profile)
                .selectinload(UserProfile.followers)
            ]
        )

        mapping_profiles: List[UserProfile] = await crud_user_profile.list(
            conditions=(
                UserProfile.id.in_(mapping_profile_ids),
                UserProfile.is_active == 1
            ),
            options=[selectinload(UserProfile.followers)]
        )

        for p in mapping_profiles:
            room.user_profiles.append(
                ChatRoomUserAssociation(room_id=room.id, user_profile_id=p.id)
            )
        await session.commit()

        room: ChatRoom = await crud_room.get(
            conditions=(ChatRoom.id == room.id,),
            options=[
                selectinload(ChatRoom.user_profiles)
                .joinedload(ChatRoomUserAssociation.user_profile)
                .selectinload(UserProfile.images),
                selectinload(ChatRoom.user_profiles)
                .joinedload(ChatRoomUserAssociation.user_profile)
                .selectinload(UserProfile.followers)
            ]
        )
        # Redis 데이터 업데이트
        default_profile_images: List[RedisUserImageFileS] = (
            await redis_hdr.generate_profile_images_schema(
                [m.user_profile for m in room.user_profiles], only_default=True
            )
        )
        user_profile_ids = []
        async with await redis_hdr.pipeline() as pipe:
            for m in room.user_profiles:
                user_profile_ids.append(m.user_profile_id)
                async with await redis_hdr.lock(
                    key=RedisChatRoomsByUserProfileS.get_lock_key(m.user_profile_id)
                ):
                    rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = (
                        await RedisChatRoomsByUserProfileS.zrange(await redis_hdr.redis, m.user_profile_id)
                    )
                    filtered_rooms_by_profile_redis = [r for r in rooms_by_profile_redis if r.id == room.id]
                    if filtered_rooms_by_profile_redis:
                        await RedisChatRoomsByUserProfileS.zrem(
                            pipe, m.user_profile_id, *filtered_rooms_by_profile_redis
                        )
                    pipe = await RedisChatRoomsByUserProfileS.zadd(
                        pipe, m.user_profile_id, RedisChatRoomByUserProfileS(
                            id=room.id,
                            unread_msg_cnt=0,
                            timestamp=now.timestamp()
                        )
                    )
                async with await redis_hdr.lock(
                    key=RedisUserProfilesByRoomS.get_lock_key((room.id, m.user_profile_id))
                ):
                    profiles_by_room_redis: List[RedisUserProfileByRoomS] = (
                        await RedisUserProfilesByRoomS.smembers(await redis_hdr.redis, (room.id, m.user_profile_id))
                    )
                    filtered_profiles_by_room_redis = [
                        p for p in profiles_by_room_redis
                        if p.id in [n.user_profile_id for n in room.user_profiles]
                    ]
                    if filtered_profiles_by_room_redis:
                        pipe = await RedisUserProfilesByRoomS.srem(
                            pipe, (room.id, m.user_profile_id), *filtered_profiles_by_room_redis
                        )
                    pipe = await RedisUserProfilesByRoomS.sadd(
                        pipe, (room.id, m.user_profile_id), *[
                            RedisUserProfilesByRoomS.schema(
                                id=n.user_profile_id,
                                identity_id=n.user_profile.identity_id,
                                nickname=n.user_profile.get_nickname_by_other(m.user_profile_id),
                                files=[im for im in default_profile_images if im.user_profile_id == n.user_profile_id]
                            ) for n in room.user_profiles
                        ]
                    )

            await RedisInfoByRoomS.hset(pipe, room.id, data=RedisChatRoomInfoS(
                id=room.id,
                type=room.type.name.lower(),
                user_profile_ids=user_profile_ids,
                user_profile_files=default_profile_images,
                connected_profile_ids=[],
            ))
            await pipe.execute()
    finally:
        await redis_hdr.close()

    return ChatRoomS.from_orm(room)


@router.websocket('/conversation/{user_profile_id}/{room_id}')
async def chat(
    websocket: WebSocket,
    user_profile_id: int,
    room_id: int
):
    """
    대화 방 입장 및 실시간 채팅
    """
    def get_log_error(exc: BaseException):
        return (
            f'Chat Error - room_id: {room_id}, user_profile_id: {user_profile_id}, '
            f'reason: {ExceptionHandler(exc).error}'
        )

    redis_hdr = RedisHandler()

    ws_handler = WebSocketHandler(websocket)
    await ws_handler.accept()
    async with async_session() as session:
        try:
            try:
                user: User = await AuthValidator(session).get_user_by_websocket(websocket)
                if not next((p for p in user.profiles if p.id == user_profile_id), None):
                    raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
            except:
                raise WebSocketDisconnect(
                    code=status.WS_1008_POLICY_VIOLATION, reason=ResponseCode.UNAUTHORIZED.value
                )

            # 방 데이터 추출
            try:
                room_redis, _ = await redis_hdr.get_room(room_id, ChatRoomCRUD(session), sync=True)
            except Exception as e:
                raise WebSocketDisconnect(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason=f'Not exist room. {e}'
                )

            # 유저가 속한 방 데이터 추출
            try:
                room_by_profile_redis, _ = await redis_hdr.get_room_by_user_profile(
                    room_id, user_profile_id, ChatRoomUserAssociationCRUD(session), sync=True, raise_exception=True
                )
            except Exception as e:
                raise WebSocketDisconnect(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason=f'Not exist room by user. {e}'
                )

            # 방에 속한 유저들 프로필 데이터 추출
            try:
                user_profiles_redis, _ = await redis_hdr.get_user_profiles_in_room(
                    room_id, user_profile_id, ChatRoomUserAssociationCRUD(session), sync=True, raise_exception=True
                )
            except Exception as e:
                raise WebSocketDisconnect(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason=f'Failed to get user profiles in the room. {e}'
                )
            else:
                # 방에 해당 유저 존재 여부 확인
                if not next((p for p in user_profiles_redis if p.id == user_profile_id), None):
                    raise WebSocketDisconnect(
                        code=status.WS_1011_INTERNAL_ERROR,
                        reason='Not exist the user in the room.'
                    )

        except Exception as e:
            code = e.code if isinstance(e, WebSocketDisconnect) else status.WS_1011_INTERNAL_ERROR
            reason = ExceptionHandler(e).error
            logger.exception(get_log_error(e))
            await ws_handler.close(code=code, reason=reason)
            raise WebSocketDisconnect(code=code, reason=reason)

    async def producer_handler(pub: Redis, ws: WebSocket):
        raised_errors = set()

        try:
            async with async_session() as session:
                crud_room = ChatRoomCRUD(session)
                crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)

                # 방 데이터 추출
                try:
                    room_redis, _ = await redis_hdr.get_room(
                        room_id, crud_room, sync=True, raise_exception=True
                    )
                except Exception as exc:
                    raise WebSocketDisconnect(
                        code=status.WS_1011_INTERNAL_ERROR,
                        reason=f'Failed to get room. {exc}'
                    )
                # 유저에 연결된 방 데이터 추출
                try:
                    room_by_profile_redis, _ = await redis_hdr.get_room_by_user_profile(
                        room_id, user_profile_id, crud_room_user_mapping,
                        sync=True, raise_exception=True
                    )
                except Exception as exc:
                    raise WebSocketDisconnect(
                        code=status.WS_1011_INTERNAL_ERROR,
                        reason=f'Failed to get room for user profile. {exc}'
                    )

                # 방에 웹소켓 연결된 유저 프로필 ID 추가
                room_redis.add_connected_profile_id(user_profile_id)
                await RedisInfoByRoomS.hset(
                    await redis_hdr.redis, room_id,
                    field='connected_profile_ids', value=room_redis.connected_profile_ids
                )

                # 채팅방 unread_msg_cnt = 0 설정 (채팅방 접속 시, 모두 읽음 처리)
                if room_by_profile_redis.unread_msg_cnt > 0:
                    async with await redis_hdr.lock(
                        key=RedisChatRoomsByUserProfileS.get_lock_key(user_profile_id)
                    ):
                        async with await redis_hdr.pipeline() as pipe:
                            pipe = await RedisChatRoomsByUserProfileS.zrem(
                                pipe, user_profile_id, room_by_profile_redis
                            )
                            room_by_profile_redis.unread_msg_cnt = 0
                            pipe = await RedisChatRoomsByUserProfileS.zadd(
                                pipe, user_profile_id, room_by_profile_redis
                            )
                            await pipe.execute()

                async with await redis_hdr.lock(key=RedisChatHistoriesByRoomS.get_lock_key(room_id)):
                    chat_histories_redis: List[RedisChatHistoryByRoomS] = (
                        await RedisChatHistoriesByRoomS.zrevrange(await redis_hdr.redis, room_id)
                    )
                    target_histories_redis: List[Tuple[RedisChatHistoryByRoomS, List[int]]] = []
                    # 최근 읽음 처리 동기화 안된 채팅 내역 추출
                    for h in chat_histories_redis:
                        if (
                            len(set(h.read_user_ids) & set(room_redis.connected_profile_ids))
                            != len(room_redis.connected_profile_ids)
                        ):
                            sync_read_user_ids = list(set(h.read_user_ids) | set(room_redis.connected_profile_ids))
                            target_histories_redis.append((h, sync_read_user_ids))
                        else:
                            break

                    # 채팅 내역 읽음 처리
                    if target_histories_redis:
                        async with await redis_hdr.pipeline() as pipe:
                            unsync, sync = [], []
                            patch_histories_redis = []
                            async for history, read_user_ids in async_iter(target_histories_redis):
                                unsync.append(deepcopy(history))
                                history.read_user_ids = read_user_ids
                                sync.append(history)
                                patch_histories_redis.append(RedisChatHistoryPatchS(
                                    id=history.id,
                                    redis_id=history.redis_id,
                                    user_profile_id=history.user_profile_id,
                                    is_active=history.is_active,
                                    read_user_ids=history.read_user_ids
                                ))
                            pipe = await RedisChatHistoriesByRoomS.zrem(pipe, room_id, *unsync)
                            pipe = await RedisChatHistoriesByRoomS.zadd(pipe, room_id, sync)
                            await pipe.execute()

                        await pub.publish(f'pubsub:room:{room_id}:chat', ChatSendFormS(
                            type=ChatType.UPDATE,
                            data=ChatSendDataS(patch_histories=patch_histories_redis)
                        ).json())

            while True:
                data = await ws_handler.receive_json()
                if not data:
                    continue

                async with async_session() as session:
                    try:
                        crud_room = ChatRoomCRUD(session)
                        crud_chat_history = ChatHistoryCRUD(session)
                        crud_history_user_mapping = ChatHistoryUserAssociationCRUD(session)
                        crud_user_profile = UserProfileCRUD(session)
                        crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)

                        # 방 데이터 추출
                        try:
                            room_redis, _ = await redis_hdr.get_room(
                                room_id, crud_room, sync=True, raise_exception=True
                            )
                        except Exception as exc:
                            raise WebSocketDisconnect(
                                code=status.WS_1011_INTERNAL_ERROR,
                                reason=f'Failed to get room. {exc}'
                            )
                        # 유저에 연결된 방 데이터 추출
                        try:
                            room_by_profile_redis, _ = await redis_hdr.get_room_by_user_profile(
                                room_id, user_profile_id, crud_room_user_mapping, sync=True, raise_exception=True
                            )
                        except Exception as exc:
                            raise WebSocketDisconnect(
                                code=status.WS_1011_INTERNAL_ERROR,
                                reason=f'Failed to get room for user profile. {exc}'
                            )
                        # 방에 속한 유저들 프로필 데이터 추출
                        try:
                            user_profiles_redis, _ = await redis_hdr.get_user_profiles_in_room(
                                room_id, user_profile_id, crud_room_user_mapping, sync=True, raise_exception=True
                            )
                        except Exception as exc:
                            raise WebSocketDisconnect(
                                code=status.WS_1011_INTERNAL_ERROR,
                                reason=f'Failed to get user profiles in the room. {exc}'
                            )
                        # 방에 해당 유저 존재 여부 확인
                        user_profile_redis: RedisUserProfileByRoomS = next(
                            (p for p in user_profiles_redis if p.id == user_profile_id), None
                        )
                        if not user_profile_redis:
                            raise WebSocketDisconnect(
                                code=status.WS_1011_INTERNAL_ERROR,
                                reason='Left the chat room.'
                            )

                        now = datetime.now().astimezone()
                        # 요청 데이터 확보
                        request_s = ChatReceiveFormS(**data)
                        # Unicast 응답 데이터 초기화
                        unicast_response_s: Optional[ChatSendFormS] = None
                        # Broadcast 응답 데이터 초기화
                        broadcast_response_s: Optional[ChatSendFormS] = None

                        # 대화 내용 조회
                        if request_s.type == ChatType.LOOKUP:
                            if request_s.data.offset is None or request_s.data.limit is None:
                                logger.warning("Not exists offset or limit for page.")
                                continue

                            # Redis 대화 내용 조회
                            chat_histories_redis: List[RedisChatHistoryByRoomS] = (
                                await RedisChatHistoriesByRoomS.zrevrange(
                                    pub, room_id,
                                    start=request_s.data.offset,
                                    end=request_s.data.offset + request_s.data.limit - 1
                                )
                            )
                            # Redis 데이터 없는 경우 DB 조회
                            lack_cnt: int = request_s.data.limit - len(chat_histories_redis)
                            migrated_chat_histories_redis: List[RedisChatHistoryByRoomS] = []
                            if lack_cnt > 0:
                                if chat_histories_redis:
                                    next_offset: int = request_s.data.offset + len(chat_histories_redis)
                                else:
                                    next_offset: int = request_s.data.offset
                                chat_histories_db: List[ChatHistory] = await crud_chat_history.list(
                                    conditions=(ChatHistory.room_id == room_id,),
                                    offset=next_offset,
                                    limit=lack_cnt,
                                    order_by=(ChatHistory.created.desc(),),
                                    options=[
                                        selectinload(ChatHistory.user_profile_mapping),
                                        selectinload(ChatHistory.files),
                                        joinedload(ChatHistory.user_profile)
                                        .selectinload(UserProfile.images),
                                        joinedload(ChatHistory.user_profile)
                                        .selectinload(UserProfile.followers)
                                    ]
                                )
                                # 채팅 읽은 유저의 DB 정보 업데이트 및 생성
                                if chat_histories_db:
                                    create_target_db: List[ChatHistory] = []
                                    update_target_db: List[ChatHistoryUserAssociation] = []
                                    for h in chat_histories_db:
                                        if not h.user_profile_mapping:
                                            create_target_db.append(h)
                                        else:
                                            m = next((
                                                m for m in h.user_profile_mapping
                                                if m.user_profile_id == user_profile_id), None)
                                            if m:
                                                if not m.is_read:
                                                    update_target_db.append(m)
                                            else:
                                                create_target_db.append(h)
                                    if create_target_db:
                                        await crud_history_user_mapping.bulk_create([
                                            dict(
                                                history_id=h.id,
                                                user_profile_id=user_profile_id
                                            ) for h in create_target_db
                                        ])
                                        await session.commit()
                                    if update_target_db:
                                        await crud_history_user_mapping.bulk_update([
                                            dict(id=m.id, is_read=True) for m in update_target_db
                                        ])
                                        await session.commit()

                                    for h in chat_histories_db:
                                        migrated_chat_histories_redis.append(RedisChatHistoryByRoomS(
                                            id=h.id,
                                            redis_id=h.redis_id,
                                            user_profile_id=h.user_profile_id,
                                            contents=h.contents,
                                            type=h.type.name.lower(),
                                            files=await redis_hdr.generate_files_schema(
                                                ChatHistoryFile, h.files, presigned=True
                                            ),
                                            read_user_ids=[
                                                m.user_profile_id for m in h.user_profile_mapping if m.is_read
                                            ],
                                            timestamp=h.created.timestamp(),
                                            date=now.date().isoformat(),
                                            is_active=h.is_active
                                        ))

                            if migrated_chat_histories_redis:
                                chat_histories_redis.extend(migrated_chat_histories_redis)
                            chat_histories_redis.sort(key=lambda x: x.timestamp)

                            unicast_response_s = ChatSendFormS(
                                type=ChatType.LOOKUP,
                                data=ChatSendDataS(histories=chat_histories_redis)
                            )

                        # 업데이트 요청
                        elif request_s.type == ChatType.UPDATE:
                            patch_histories_redis: List[RedisChatHistoryPatchS] = []
                            # 채팅 내역 상태를 업데이트 하는 경우
                            if not request_s.data.history_redis_ids:
                                logger.warning("Not exists chat history redis ids.")
                                continue

                            # 업데이트 필요한 필드 확인
                            update_fields = (ChatHistory.is_active.name,)
                            update_target_redis: List[RedisChatHistoryByRoomS] = []
                            update_target_db: List[str] = []
                            update_values_db: Dict[str, Any] = {}

                            async with await redis_hdr.lock(key=RedisChatHistoriesByRoomS.get_lock_key(room_id)):
                                chat_histories_redis: List[RedisChatHistoryByRoomS] = (
                                    await RedisChatHistoriesByRoomS.zrevrange(pub, room_id)
                                )
                                if not chat_histories_redis:
                                    logger.warning("Not exists chat histories in the room. room_id: %s", room_id)
                                    continue

                                async with await redis_hdr.pipeline() as pipe:
                                    for redis_id in request_s.data.history_redis_ids:
                                        duplicated_histories_redis: List[RedisChatHistoryByRoomS] = [
                                            h for h in chat_histories_redis if h.redis_id == redis_id
                                        ]
                                        history_redis: RedisChatHistoryByRoomS = (
                                            duplicated_histories_redis and duplicated_histories_redis[0]
                                        )
                                        copied_history_redis: RedisChatHistoryByRoomS = (
                                            history_redis and deepcopy(history_redis)
                                        )
                                        update_redis = False
                                        for f in update_fields:
                                            if getattr(request_s.data, f) is None:
                                                continue
                                            if duplicated_histories_redis:
                                                # 기존 데이터와 다른 경우 업데이트 설정
                                                if getattr(request_s.data, f) != getattr(
                                                    duplicated_histories_redis[0], f
                                                ):
                                                    setattr(copied_history_redis, f, getattr(request_s.data, f))
                                                    update_redis = True
                                            else:
                                                update_values_db.update({f: getattr(request_s.data, f)})
                                        if update_redis:
                                            update_target_redis.append(copied_history_redis)
                                            pipe = await RedisChatHistoriesByRoomS.zrem(
                                                pipe, room_id, *duplicated_histories_redis
                                            )
                                        if update_values_db:
                                            update_target_db.append(redis_id)
                                    # Redis 에 저장되어 있는 데이터 업데이트
                                    if update_target_redis:
                                        pipe = await redis_hdr.update_histories_by_room(
                                            room_id, update_target_redis, pipe
                                        )
                                        await pipe.execute()
                                        for h in update_target_redis:
                                            patch_histories_redis.append(RedisChatHistoryPatchS(
                                                id=h.id,
                                                redis_id=h.redis_id,
                                                user_profile_id=h.user_profile_id,
                                                is_active=h.is_active,
                                                read_user_ids=h.read_user_ids
                                            ))

                            # Redis 에 저장되어 있지 않은 history_ids 에 한해 DB 업데이트
                            if update_target_db:
                                await crud_chat_history.update(
                                    conditions=(ChatHistory.redis_id.in_(update_target_db),),
                                    **update_values_db
                                )
                                await session.commit()
                                updated_histories_db: List[ChatHistory] = await crud_chat_history.list(
                                    conditions=(ChatHistory.redis_id.in_(update_target_db),),
                                    options=[selectinload(ChatHistory.user_profile_mapping)]
                                )
                                for h in updated_histories_db:
                                    patch_histories_redis.append(RedisChatHistoryPatchS(
                                        id=h.id,
                                        redis_id=h.redis_id,
                                        user_profile_id=h.user_profile_id,
                                        is_active=h.is_active,
                                        read_user_ids=[
                                            m.user_profile_id for m in h.user_profile_mapping if m.is_read
                                        ]
                                    ))

                            broadcast_response_s = ChatSendFormS(
                                type=request_s.type,
                                data=ChatSendDataS(patch_histories=patch_histories_redis)
                            )
                        # 메시지 요청
                        elif request_s.type == ChatType.MESSAGE:
                            # Redis 저장
                            chat_history_redis: RedisChatHistoryByRoomS = RedisChatHistoryByRoomS(
                                redis_id=uuid.uuid4().hex,
                                user_profile_id=user_profile_id,
                                contents=request_s.data.text,
                                type=ChatHistoryType.MESSAGE.name.lower(),
                                read_user_ids=list({user_profile_id} | set(room_redis.connected_profile_ids)),
                                timestamp=now.timestamp(),
                                date=now.date().isoformat(),
                                is_active=True
                            )
                            await RedisChatHistoriesByRoomS.zadd(pub, room_id, chat_history_redis)

                            # 각 유저 별 해당 방의 unread_msg_cnt 업데이트
                            for p in user_profiles_redis:
                                if p.id not in room_redis.connected_profile_ids:
                                    await redis_hdr.update_unread_msg_cnt(
                                        room_id,
                                        p.id,
                                        crud_room_user_mapping
                                    )

                            broadcast_response_s = ChatSendFormS(
                                type=request_s.type,
                                data=ChatSendDataS(history=chat_history_redis)
                            )
                        # 파일 업로드 요청
                        elif request_s.type == ChatType.FILE:
                            redis_id = uuid.uuid4().hex
                            chat_history_db: ChatHistory = await crud_chat_history.create(
                                redis_id=redis_id,
                                room_id=room_id,
                                user_profile_id=user_profile_id,
                                type=ChatHistoryType.FILE
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
                                uploaded_by_id=user_profile_id,
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
                            except Exception as exc:
                                logger.error(f'Failed to upload files: {exc}')
                                continue
                            finally:
                                for o in chat_files_db:
                                    o.close()

                            session.add_all(chat_files_db)
                            await session.commit()
                            for o in chat_files_db:
                                await session.refresh(o)

                            files_s: List[RedisChatHistoryFileS] = await redis_hdr.generate_files_schema(
                                ChatHistoryFile, chat_files_db, presigned=True
                            )
                            chat_history_redis: RedisChatHistoryByRoomS = RedisChatHistoryByRoomS(
                                id=chat_history_db.id,
                                redis_id=redis_id,
                                user_profile_id=user_profile_id,
                                files=files_s,
                                read_user_ids=list({user_profile_id} | set(room_redis.connected_profile_ids)),
                                type=chat_history_db.type.name.lower(),
                                timestamp=now.timestamp(),
                                date=now.date().isoformat(),
                                is_active=chat_history_db.is_active
                            )
                            await RedisChatHistoriesByRoomS.zadd(pub, room_id, chat_history_redis)

                            # 각 유저 별 해당 방의 unread_msg_cnt 업데이트
                            for p in user_profiles_redis:
                                if p.id not in room_redis.connected_profile_ids:
                                    await redis_hdr.update_unread_msg_cnt(
                                        room_id,
                                        p.id,
                                        crud_room_user_mapping
                                    )

                            broadcast_response_s = ChatSendFormS(
                                type=request_s.type,
                                data=ChatSendDataS(history=chat_history_redis)
                            )

                        # 유저 초대
                        elif request_s.type == ChatType.INVITE:
                            target_profile_ids: List[int] = request_s.data.target_profile_ids
                            if not target_profile_ids:
                                continue

                            _room_user_mapping: List[ChatRoomUserAssociation] = (
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
                            )
                            # 방에 속한 유저 -> Redis, DB 동기화
                            current_profiles: List[UserProfile] = [m.user_profile for m in _room_user_mapping]
                            current_profile_images_redis: List[RedisUserImageFileS] = (
                                await redis_hdr.generate_profile_images_schema(
                                    current_profiles, only_default=True
                                )
                            )
                            current_profile_ids: Set[int] = {p.id for p in current_profiles}
                            for current_id in current_profile_ids:
                                async with await redis_hdr.lock(
                                    key=RedisUserProfilesByRoomS.get_lock_key((room_id, current_id))
                                ):
                                    _user_profiles_redis: List[RedisUserProfileByRoomS] = (
                                        await RedisUserProfilesByRoomS.smembers(
                                            pub, (room_id, current_id)
                                        )
                                    )
                                    if len(_user_profiles_redis) != len(_room_user_mapping):
                                        async with await redis_hdr.pipeline() as pipe:
                                            pipe = await RedisUserProfilesByRoomS.srem(
                                                pipe, (room_id, current_id), *_user_profiles_redis
                                            )
                                            pipe = await RedisUserProfilesByRoomS.sadd(
                                                pipe, (room_id, current_id), *[
                                                    RedisUserProfilesByRoomS.schema(
                                                        id=m.user_profile.id,
                                                        identity_id=m.user_profile.identity_id,
                                                        nickname=m.user_profile.get_nickname_by_other(current_id),
                                                        files=[
                                                            im for im in current_profile_images_redis
                                                            if im.user_profile_id == m.user_profile_id]
                                                    ) for m in _room_user_mapping
                                                ]
                                            )
                                            await pipe.execute()

                            add_profile_ids: Set[int] = set(target_profile_ids)
                            profile_ids: Set[int] = add_profile_ids - current_profile_ids
                            if not profile_ids:
                                continue
                            profiles: List[UserProfile] = await crud_user_profile.list(
                                conditions=(
                                    UserProfile.id.in_(profile_ids),
                                    UserProfile.is_active == 1
                                ),
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

                            total_profiles: List[UserProfile] = current_profiles + profiles
                            profile_images_redis: List[RedisUserImageFileS] = (
                                await redis_hdr.generate_profile_images_schema(profiles, only_default=True)
                            )
                            total_profile_images_redis: List[RedisUserImageFileS] = (
                                current_profile_images_redis + profile_images_redis
                            )

                            # 방 정보 업데이트
                            async with await redis_hdr.lock(key=RedisInfoByRoomS.get_lock_key()):
                                async with await redis_hdr.pipeline() as pipe:
                                    room_redis.user_profile_ids = [p.id for p in total_profiles]
                                    room_redis.user_profile_files = total_profile_images_redis
                                    await RedisInfoByRoomS.hset(await redis_hdr.redis, room_id, data=room_redis)
                                    await pipe.execute()

                            for target_profile in total_profiles:
                                # 각 방에 있는 유저 기준으로 데이터 업데이트
                                async with await redis_hdr.lock(
                                    key=RedisUserProfilesByRoomS.get_lock_key((room_id, target_profile.id))
                                ):
                                    await RedisUserProfilesByRoomS.sadd(
                                        pub, (room_id, target_profile.id), *[
                                            RedisUserProfilesByRoomS.schema(
                                                id=p.id,
                                                identity_id=p.identity_id,
                                                nickname=p.get_nickname_by_other(target_profile.id),
                                                files=[
                                                    im for im in total_profile_images_redis
                                                    if im.user_profile_id == p.id
                                                ]
                                            ) for p in (total_profiles if target_profile in profiles else profiles)
                                        ]
                                    )
                                # 각 유저 기준으로 방 정보 없다면 생성
                                async with await redis_hdr.lock(
                                    key=RedisChatRoomsByUserProfileS.get_lock_key(target_profile.id)
                                ):
                                    _room_by_profile_redis, _ = await redis_hdr.get_room_by_user_profile(
                                        room_id, target_profile.id, crud_room_user_mapping, sync=True, lock=False
                                    )
                                    if not _room_by_profile_redis:
                                        await RedisChatRoomsByUserProfileS.zadd(
                                            pub, target_profile.id, RedisChatRoomByUserProfileS(
                                                id=room_id, unread_msg_cnt=0, timestamp=now.timestamp()
                                            )
                                        )
                            # 대화방 초대 메시지 전송
                            if len(profiles) > 1:
                                target_msg = '님과 '.join([p.nickname for p in profiles])
                            else:
                                target_msg = profiles[0].nickname

                            chat_history_redis: RedisChatHistoryByRoomS = RedisChatHistoryByRoomS(
                                redis_id=uuid.uuid4().hex,
                                user_profile_id=user_profile_id,
                                contents=f'{user_profile_redis.nickname}님이 {target_msg}님을 초대했습니다.',
                                type=ChatHistoryType.NOTICE.name.lower(),
                                read_user_ids=list({user_profile_id} | set(room_redis.connected_profile_ids)),
                                timestamp=now.timestamp(),
                                date=now.date().isoformat(),
                                is_active=True
                            )
                            await RedisChatHistoriesByRoomS.zadd(pub, room_id, chat_history_redis)

                            broadcast_response_s = ChatSendFormS(
                                type=request_s.type,
                                data=ChatSendDataS(history=chat_history_redis)
                            )
                        # 연결 종료
                        elif request_s.type == ChatType.TERMINATE:
                            try:
                                room_user_mappings_db: List[ChatRoomUserAssociation] = (
                                    await crud_room_user_mapping.list(
                                        conditions=(
                                            ChatRoomUserAssociation.room_id == room_id,
                                        ),
                                        options=[
                                            joinedload(ChatRoomUserAssociation.room)
                                            .selectinload(ChatRoom.user_profiles),
                                            joinedload(ChatRoomUserAssociation.user_profile)
                                        ]
                                    )
                                )
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
                                        ChatRoomUserAssociation.user_profile_id == user_profile_id)
                                    )
                            finally:
                                async with await redis_hdr.pipeline() as pipe:
                                    rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = (
                                        await RedisChatRoomsByUserProfileS.zrange(pub, user_profile_id)
                                    )
                                    pipe = await RedisChatRoomsByUserProfileS.zrem(
                                        pipe, user_profile_id, *[
                                            r for r in rooms_by_profile_redis if r.id == room_id
                                        ]
                                    )

                                    for profile_id in room_redis.user_profile_ids:
                                        if profile_id == user_profile_id:
                                            pipe = await RedisUserProfilesByRoomS.delete(
                                                pipe, (room_id, user_profile_id)
                                            )
                                        else:
                                            async with await redis_hdr.lock(
                                                key=RedisUserProfilesByRoomS.get_lock_key((room_id, profile_id))
                                            ):
                                                profiles_redis: List[RedisUserProfileByRoomS] = (
                                                    await RedisUserProfilesByRoomS.smembers(
                                                        pub, (room_id, profile_id)
                                                    )
                                                )
                                                remove_profile_redis: List[RedisUserProfileByRoomS] = [
                                                    p for p in profiles_redis if p.id == user_profile_id
                                                ]
                                                pipe = await RedisUserProfilesByRoomS.srem(
                                                    pipe, (room_id, profile_id), *remove_profile_redis
                                                )

                                    async with await redis_hdr.lock(key=RedisInfoByRoomS.get_lock_key()):
                                        if not room_db.is_active:
                                            await RedisInfoByRoomS.delete(await redis_hdr.redis, room_id)
                                        else:
                                            room_redis.user_profile_ids = [
                                                i for i in room_redis.user_profile_ids if i != user_profile_id
                                            ]
                                            room_redis.user_profile_files = [
                                                f for f in room_redis.user_profile_files
                                                if f.user_profile_id != user_profile_id
                                            ]
                                            await RedisInfoByRoomS.hset(await redis_hdr.redis, room_id, data=room_redis)

                                    chat_history_redis: RedisChatHistoryByRoomS = RedisChatHistoryByRoomS(
                                        redis_id=uuid.uuid4().hex,
                                        user_profile_id=user_profile_id,
                                        contents=f'{user_profile_redis.nickname}님이 나갔습니다.',
                                        type=ChatHistoryType.NOTICE.name.lower(),
                                        read_user_ids=list({user_profile_id} | set(room_redis.connected_profile_ids)),
                                        timestamp=now.timestamp(),
                                        date=now.date().isoformat(),
                                        is_active=True
                                    )
                                    await RedisChatHistoriesByRoomS.zadd(
                                        pub, room_id, chat_history_redis
                                    )
                                    broadcast_response_s = ChatSendFormS(
                                        type=ChatType.TERMINATE,
                                        data=ChatSendDataS(history=chat_history_redis)
                                    )
                                    await session.commit()
                                    await pipe.execute()
                                    await ws_handler.close(code=status.WS_1001_GOING_AWAY, reason='Self terminated.')
                        else:
                            await ws_handler.send_text('pong')
                            continue

                        if unicast_response_s:
                            await ws_handler.send_json(jsonable_encoder(unicast_response_s))
                        if broadcast_response_s:
                            await pub.publish(f'pubsub:room:{room_id}:chat', broadcast_response_s.json())

                    except (WebSocketDisconnect, WebSocketException) as exc:
                        raise exc
                    except Exception as exc:
                        if exc.__class__.__name__ not in raised_errors:
                            logger.error(get_log_error(exc))
                            raised_errors.add(exc.__class__.__name__)
        except (WebSocketDisconnect, WebSocketException) as exc:
            await ws_handler.close(e=exc)
            if not ws_handler.self_disconnected(exc):
                logger.exception(get_log_error(exc))
            raise exc

    async def consumer_handler(psub: PubSub, ws: WebSocket):
        raised_errors = set()

        try:
            async with psub as p:
                await p.subscribe(f'pubsub:room:{room_id}:chat')
                try:
                    while True:
                        message: dict = await p.get_message(ignore_subscribe_messages=True)
                        if message:
                            await ws_handler.send_json(json.loads(message.get('data')))
                except asyncio.CancelledError as exc:
                    await p.unsubscribe()
                    raise exc
                except Exception as exc:
                    if exc.__class__.__name__ not in raised_errors:
                        logger.error(get_log_error(exc))
                        raised_errors.add(exc.__class__.__name__)
        except asyncio.CancelledError as exc:
            await psub.close()
            logger.error(get_log_error(exc))

    try:
        await redis_hdr.handle_pubsub(websocket, producer_handler, consumer_handler)
    finally:
        room_redis.connected_profile_ids = [
            profile_id for profile_id in room_redis.connected_profile_ids
            if profile_id != user_profile_id
        ]
        await RedisInfoByRoomS.hset(
            await redis_hdr.redis, room_id,
            field='connected_profile_ids', value=room_redis.connected_profile_ids
        )
        await redis_hdr.close()


@router.websocket('/followings/{user_profile_id}')
async def chat_followings(
    websocket: WebSocket,
    user_profile_id: int
):
    """
    친구 목록 조회
    """
    def get_log_error(exc: BaseException):
        return (
            f'Followings Error - user_profile_id: {user_profile_id}, '
            f'reason: {ExceptionHandler(exc).error}'
        )

    ws_handler = WebSocketHandler(websocket)
    await ws_handler.accept()
    async with async_session() as session:
        try:
            user: User = await AuthValidator(session).get_user_by_websocket(websocket)
            user_profile: UserProfile = next((p for p in user.profiles if p.id == user_profile_id and p.is_active), None)
            if not user_profile:
                raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
        except:
            code = status.WS_1008_POLICY_VIOLATION
            reason = ResponseCode.UNAUTHORIZED.value
            await ws_handler.close(code=code, reason=reason)
            raise WebSocketDisconnect(code=code, reason=reason)

    async def producer_handler():
        while True:
            try:
                duplicated_followings: List[RedisFollowingByUserProfileS] = (
                    await RedisFollowingsByUserProfileS.smembers(await redis_hdr.redis, user_profile_id)
                )
                followings: List[RedisFollowingByUserProfileS] = []
                if duplicated_followings:
                    for key, items in groupby(duplicated_followings, key=lambda x: x.id):
                        followings.append(list(items)[-1])

                if not followings:
                    async with async_session() as session:
                        crud_user_profile = UserProfileCRUD(session)
                        user_profile: UserProfile = await crud_user_profile.get(
                            conditions=(
                                UserProfile.id == user_profile_id,
                                UserProfile.is_active == 1
                            ),
                            options=[
                                selectinload(UserProfile.followings)
                                .joinedload(UserRelationship.other_profile)
                                .selectinload(UserProfile.images),
                                selectinload(UserProfile.followings)
                                .joinedload(UserRelationship.other_profile)
                                .selectinload(UserProfile.followers)
                            ])
                        if user_profile.followings:
                            async with await redis_hdr.lock(
                                key=RedisFollowingsByUserProfileS.get_lock_key(user_profile_id)
                            ):
                                if not await RedisFollowingsByUserProfileS.scard(
                                    await redis_hdr.redis, user_profile_id
                                ):
                                    await RedisFollowingsByUserProfileS.sadd(await redis_hdr.redis, user_profile_id, *[
                                        RedisFollowingsByUserProfileS.schema(
                                            id=f.other_profile_id,
                                            identity_id=f.other_profile.identity_id,
                                            nickname=f.other_profile.get_nickname_by_other(user_profile_id),
                                            type=f.type.name.lower(),
                                            favorites=f.favorites,
                                            is_hidden=f.is_hidden,
                                            is_forbidden=f.is_forbidden,
                                            files=await redis_hdr.generate_files_schema(
                                                UserProfileImage, [i for i in f.other_profile.images if i.is_default]
                                            )
                                        ) for f in user_profile.followings
                                    ])
                await ws_handler.send_json(jsonable_encoder(followings))
            except (WebSocketDisconnect, WebSocketException) as e:
                await ws_handler.close(e=e)
                if not ws_handler.self_disconnected(e):
                    logger.exception(get_log_error(e))
                raise e
            except Exception as e:
                if e.__class__.__name__ not in raised_errors:
                    logger.exception(get_log_error(e))
                    raised_errors.add(e.__class__.__name__)

    async def consumer_handler():
        while True:
            data = await ws_handler.receive_json()
            if data:
                request_s = ChatReceiveFormS(**data)
                if request_s.type == ChatType.PING:
                    await ws_handler.send_text('pong')

    raised_errors = set()
    redis_hdr = RedisHandler()
    try:
        done, pending = await asyncio.wait([
            producer_handler(), consumer_handler()
        ], return_when=asyncio.FIRST_COMPLETED)

        if pending:
            for task in pending:
                task.cancel()
    finally:
        await redis_hdr.close()
