import asyncio
import json
import logging
from copy import deepcopy
from datetime import datetime
from itertools import groupby
from typing import List, Set, Dict, Any, Tuple

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
from server.api.websocket.chat.file import FileHandler
from server.api.websocket.chat.invite import InviteHandler
from server.api.websocket.chat.lookup import LookUpHandler
from server.api.websocket.chat.message import MessageHandler
from server.api.websocket.chat.ping import PingHandler
from server.api.websocket.chat.proxy import ChatHandlerProxy
from server.api.websocket.chat.terminate import TerminateHandler
from server.api.websocket.chat.update import UpdateHandler
from server.core.authentications import cookie, RoleChecker
from server.core.enums import UserType, ChatType, SendMessageType
from server.core.exceptions import ExceptionHandler
from server.core.externals.redis.schemas import (
    RedisUserProfilesByRoomS,
    RedisChatHistoriesByRoomS, RedisUserProfileByRoomS, RedisChatHistoryByRoomS,
    RedisChatRoomsByUserProfileS, RedisFollowingsByUserProfileS,
    RedisFollowingByUserProfileS, RedisUserImageFileS, RedisChatRoomByUserProfileS, RedisChatHistoryPatchS,
    RedisInfoByRoomS, RedisChatRoomInfoS, RedisChatRoomPubSubS, RedisChatRoomListS
)
from server.core.utils import async_iter
from server.crud.service import (
    ChatRoomUserAssociationCRUD, ChatRoomCRUD
)
from server.crud.user import UserProfileCRUD
from server.db.databases import get_async_session, async_session
from server.models import (
    User, UserProfile, ChatRoom, ChatRoomUserAssociation, UserRelationship
)
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
        room_by_profile_redis, _ = await redis_hdr.sync_room_by_user_profile(
            room_id, user_profile_id,
            crud=ChatRoomUserAssociationCRUD(session),
            raise_exception=True
        )
        profiles_by_room_redis: List[RedisUserProfileByRoomS] = await RedisUserProfilesByRoomS.smembers(
            await redis_hdr.redis, (room_id, user_profile_id)
        )
        room_name: str | None = (
            room_by_profile_redis.name
            or RedisUserProfileByRoomS.get_default_room_name(user_profile_id, profiles_by_room_redis)
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
            await AuthValidator(session).validate_profile_by_websocket(websocket, user_profile_id)
        except WebSocketDisconnect as e:
            await ws_handler.close(code=e.code, reason=e.reason)
            raise e

    async def producer_handler():
        while True:
            try:
                duplicated_rooms_by_profile_redis = await RedisChatRoomsByUserProfileS.zrevrange(
                    await redis_hdr.redis, user_profile_id
                )
                result = []
                if duplicated_rooms_by_profile_redis:
                    async with async_session() as session:
                        duplicated_rooms_by_profile_redis.sort(key=lambda x: (x.id, -x.timestamp))
                        rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = []
                        for key, items in groupby(duplicated_rooms_by_profile_redis, key=lambda x: x.id):
                            items = list(items)
                            rooms_by_profile_redis.append(items[0])

                        rooms_by_profile_redis.sort(key=lambda x: x.timestamp, reverse=True)

                        crud_room = ChatRoomCRUD(session)
                        for room_by_profile_redis in rooms_by_profile_redis:
                            room, _ = await redis_hdr.sync_room(
                                room_by_profile_redis.id, crud_room, lock=False
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
                                or RedisUserProfileByRoomS.get_default_room_name(
                                    user_profile_id, profiles_by_room_redis
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
                                'type': room and room.type,
                                'user_profiles': profiles_by_room_redis,
                                'user_profile_files': room and room.user_profile_files,
                                'last_chat_history': last_chat_history,
                                'last_chat_timestamp': last_chat_history and last_chat_history.timestamp
                            }))
                            result.append(RedisChatRoomListS(**obj))
                await ws_handler.send_json(jsonable_encoder(ChatSendFormS(
                    type=ChatType.LOOKUP,
                    data=ChatSendDataS(rooms=result)
                )))
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
                receive = ChatReceiveFormS(**data)
                if receive.type == ChatType.PING:
                    await ws_handler.send_json(jsonable_encoder(ChatSendFormS(
                        type=receive.type,
                        data=ChatSendDataS(pong=True)
                    )))

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
                        _, pipe = await redis_hdr.sync_room_by_user_profile(
                            room.id, profile_id, crud_room_user_mapping, pipe=pipe
                        )
                        _, pipe = await redis_hdr.sync_user_profiles_in_room(
                            room.id, profile_id, crud_room_user_mapping, pipe=pipe
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
            await RedisUserImageFileS.generate_profile_images_schema(
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
            await AuthValidator(session).validate_profile_by_websocket(websocket, user_profile_id)

            # 방 데이터 추출
            try:
                room_redis, _ = await redis_hdr.sync_room(room_id, ChatRoomCRUD(session))
            except Exception as e:
                raise WebSocketDisconnect(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason=f'Not exist room. {e}'
                )

            # 유저가 속한 방 데이터 추출
            try:
                room_by_profile_redis, _ = await redis_hdr.sync_room_by_user_profile(
                    room_id, user_profile_id, ChatRoomUserAssociationCRUD(session), raise_exception=True
                )
            except Exception as e:
                raise WebSocketDisconnect(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason=f'Not exist room by user. {e}'
                )

            # 방에 속한 유저들 프로필 데이터 추출
            try:
                user_profiles_redis, _ = await redis_hdr.sync_user_profiles_in_room(
                    room_id, user_profile_id, ChatRoomUserAssociationCRUD(session), raise_exception=True
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
            code_reason: Dict[str, Any] = ws_handler.code_reason(e)
            logger.exception(get_log_error(e))
            await ws_handler.close(**code_reason)
            raise WebSocketDisconnect(**code_reason)

    async def producer_handler(pub: Redis, ws: WebSocket):
        raised_errors = set()

        try:
            async with async_session() as session:
                crud_room = ChatRoomCRUD(session)
                crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)

                # 방 데이터 추출
                try:
                    room_redis, _ = await redis_hdr.sync_room(room_id, crud_room, raise_exception=True)
                except Exception as exc:
                    raise WebSocketDisconnect(
                        code=status.WS_1011_INTERNAL_ERROR,
                        reason=f'Failed to get room. {exc}'
                    )
                # 유저에 연결된 방 데이터 추출
                try:
                    room_by_profile_redis, _ = await redis_hdr.sync_room_by_user_profile(
                        room_id, user_profile_id, crud_room_user_mapping, raise_exception=True
                    )
                except Exception as exc:
                    raise WebSocketDisconnect(
                        code=status.WS_1011_INTERNAL_ERROR,
                        reason=f'Failed to get room for user profile. {exc}'
                    )

                # 웹소켓 연결된 유저 프로필 ID 추가
                await redis_hdr.connect_profile_by_room(user_profile_id, room_id, room_redis)

                # 채팅방 unread_msg_cnt 초기화 (채팅방 접속 시, 모두 읽음 처리)
                await redis_hdr.init_unread_msg_cnt(user_profile_id, room_by_profile_redis)

                # 채팅 내역 읽음 처리
                async with await redis_hdr.lock(key=RedisChatHistoriesByRoomS.get_lock_key(room_id)):
                    patch_histories_redis = await redis_hdr.patch_unsync_read_by_room(room_id, room_redis)
                    if patch_histories_redis:
                        await pub.publish(
                            RedisChatRoomPubSubS.get_key(room_id),
                            ChatSendFormS(
                                type=ChatType.UPDATE,
                                data=ChatSendDataS(patch_histories=patch_histories_redis)
                            ).json()
                        )

            while True:
                data = await ws_handler.receive_json()
                if not data:
                    continue

                async with async_session() as session:
                    try:
                        crud_room = ChatRoomCRUD(session)
                        crud_room_user_mapping = ChatRoomUserAssociationCRUD(session)

                        # 방 데이터 추출
                        try:
                            room_redis, _ = await redis_hdr.sync_room(room_id, crud_room, raise_exception=True)
                        except Exception as exc:
                            raise WebSocketDisconnect(
                                code=status.WS_1011_INTERNAL_ERROR,
                                reason=f'Failed to get room. {exc}'
                            )
                        # 유저에 연결된 방 데이터 추출
                        try:
                            room_by_profile_redis, _ = await redis_hdr.sync_room_by_user_profile(
                                room_id, user_profile_id, crud_room_user_mapping, raise_exception=True
                            )
                        except Exception as exc:
                            raise WebSocketDisconnect(
                                code=status.WS_1011_INTERNAL_ERROR,
                                reason=f'Failed to get room for user profile. {exc}'
                            )
                        # 방에 속한 유저들 프로필 데이터 추출
                        try:
                            user_profiles_redis, _ = await redis_hdr.sync_user_profiles_in_room(
                                room_id, user_profile_id, crud_room_user_mapping, raise_exception=True
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

                        # 요청 데이터
                        receive = ChatReceiveFormS(**data)

                        # 메시지 전송
                        await ChatHandlerProxy(receive, session).send(
                            redis_handler=redis_hdr,
                            ws_handler=ws_handler,
                            user_profile_id=user_profile_id,
                            user_profiles_redis=user_profiles_redis,
                            user_profile_redis=user_profile_redis,
                            room_id=room_id,
                            room_redis=room_redis,
                        )

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
                await p.subscribe(RedisChatRoomPubSubS.get_key(room_id))
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
        await redis_hdr.disconnect_profile_by_room(user_profile_id, room_id, room_redis)
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
            await AuthValidator(session).validate_profile_by_websocket(websocket, user_profile_id)
        except WebSocketDisconnect as e:
            await ws_handler.close(code=e.code, reason=e.reason)
            raise e

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
                                            files=await RedisUserImageFileS.generate_files_schema(
                                                [i for i in f.other_profile.images if i.is_default]
                                            )
                                        ) for f in user_profile.followings
                                    ])
                await ws_handler.send_json(jsonable_encoder(ChatSendFormS(
                    type=ChatType.LOOKUP,
                    data=ChatSendDataS(followings=followings)
                )))
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
                receive = ChatReceiveFormS(**data)
                if receive.type == ChatType.PING:
                    await ws_handler.send_json(jsonable_encoder(ChatSendFormS(
                        type=receive.type,
                        data=ChatSendDataS(pong=True)
                    )))

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
