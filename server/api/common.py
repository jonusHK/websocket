import asyncio
from copy import deepcopy
from datetime import datetime
from typing import Iterable, List, Any, Optional, Callable, Coroutine, Tuple, Awaitable
from uuid import UUID

from aioredis.client import Pipeline, Redis, PubSub
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette import status
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState
from websockets.exceptions import ConnectionClosedOK

from server.core.authentications import COOKIE_NAME, cookie, backend
from server.core.enums import ResponseCode
from server.core.exceptions import ExceptionHandler
from server.core.externals.redis import AioRedis
from server.core.externals.redis.schemas import (
    RedisChatRoomByUserProfileS, RedisChatRoomsByUserProfileS, RedisUserProfilesByRoomS,
    RedisChatHistoriesByRoomS, RedisChatHistoriesToSyncS, RedisUserImageFileS,
    RedisUserProfileByRoomS, RedisChatHistoryByRoomS, RedisInfoByRoomS,
    RedisChatRoomInfoS, RedisChatHistoryPatchS
)
from server.core.utils import async_iter
from server.crud.service import ChatRoomCRUD, ChatRoomUserAssociationCRUD
from server.models import (
    User, ChatRoomUserAssociation, UserProfile, UserSession, ChatRoom
)


class AuthValidator:

    websocket_exception = WebSocketDisconnect(
        code=status.WS_1008_POLICY_VIOLATION, reason=ResponseCode.UNAUTHORIZED.value
    )

    def __init__(self, session: AsyncSession):
        self.session = session

    @classmethod
    def get_user_profile(cls, user_session: UserSession, user_profile_id: int):
        assert hasattr(user_session, 'user') and hasattr(user_session.user, 'profiles')
        profile: UserProfile = next((
            p for p in user_session.user.profiles if p.id == user_profile_id and p.is_active),
            None
        )
        if not profile:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return profile

    async def get_user_session_by_websocket(self, websocket: WebSocket) -> User:
        signed_session_id = websocket.cookies[COOKIE_NAME]
        session_id = UUID(
            cookie.signer.loads(
                signed_session_id,
                max_age=cookie.cookie_params.max_age,
                return_timestamp=False,
            )
        )
        user_session = await backend.read(session_id, self.session)
        return user_session

    async def validate_profile_by_websocket(
        self,
        websocket: WebSocket,
        user_profile_id: int,
        e: Optional[Exception] = None
    ) -> User:
        try:
            user_session: UserSession = await self.get_user_session_by_websocket(websocket)
            user_profile: UserProfile = self.get_user_profile(user_session, user_profile_id)
        except:
            raise e if e else self.websocket_exception
        return user_profile


class RedisHandler:

    RETRY_COUNT = 5
    RETRY_DELAY = 0.2

    _redis = None

    @classmethod
    async def generate_primary_redis(cls, connections: List[Redis]):
        async for conn in async_iter(connections):
            info = await conn.info()
            if info.get('role') == 'master':
                return conn

    @staticmethod
    def get_redis_module(**kwargs):
        return AioRedis(**kwargs)

    def __init__(self, redis_coro: Optional[Awaitable[Redis]] = None, **kwargs):
        if redis_coro is None:
            redis_module = self.get_redis_module(**kwargs)
            redis_coro = self.generate_primary_redis(redis_module.connections)
        self._redis_coro = redis_coro

    @property
    async def redis(self):
        for _ in range(self.RETRY_COUNT):
            try:
                if not self._redis:
                    self._redis = await self._redis_coro
                return self._redis
            except ConnectionError:
                await asyncio.sleep(self.RETRY_DELAY)
        raise ConnectionError('No connected master node for redis.')

    async def pipeline(self):
        redis = await self.redis
        return redis.pipeline()

    async def lock(self, key: str, timeout: int = 5):
        redis = await self.redis
        return redis.lock(name=key, timeout=timeout)

    async def pubsub(self):
        redis = await self.redis
        return redis.pubsub()

    async def close(self):
        if not self._redis:
            raise RuntimeError('Redis connection not initialized.')
        await self._redis.close()

    async def sync_room(
        self,
        room_id: int,
        crud: Optional[ChatRoomCRUD] = None,
        pipe: Optional[Pipeline] = None,
        lock=True, raise_exception=False
    ) -> Tuple[RedisChatRoomInfoS, Pipeline | None]:
        async def _action():
            callback_pipe = None
            room_redis: RedisChatRoomInfoS = await RedisInfoByRoomS.hgetall(await self.redis, room_id)
            if not room_redis:
                room_db: ChatRoom = await crud.get(
                    conditions=(ChatRoom.id == room_id,),
                    options=[
                        selectinload(ChatRoom.user_profiles)
                        .joinedload(ChatRoomUserAssociation.user_profile)
                        .selectinload(UserProfile.images)
                    ]
                )
                if room_db and room_db.is_active:
                    async def _transaction(pipeline: Pipeline):
                        return await RedisInfoByRoomS.hset(
                            pipeline, room_id, data=RedisChatRoomInfoS(
                                id=room_db.id, type=room_db.type.name.lower(),
                                user_profile_ids=[m.user_profile_id for m in room_db.user_profiles],
                                user_profile_files=await RedisUserImageFileS.generate_profile_images_schema(
                                    [m.user_profile for m in room_db.user_profiles], only_default=True
                                ), connected_profile_ids=[]
                            )
                        )

                    if not pipe:
                        async with await self.pipeline() as _pipe:
                            await (await _transaction(_pipe)).execute()
                    else:
                        callback_pipe = await _transaction(pipe)

                elif raise_exception:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return room_redis, callback_pipe

        if lock:
            async with await self.lock(key=RedisInfoByRoomS.get_lock_key()):
                return await _action()
        return await _action()

    async def sync_rooms_by_user_profile(
        self,
        user_profile_id: int,
        crud: Optional[ChatRoomUserAssociationCRUD] = None,
        pipe: Optional[Pipeline] = None,
        reverse=False, lock=True, raise_exception=False
    ) -> Tuple[List[RedisChatRoomByUserProfileS], Pipeline | None]:
        now = datetime.now().astimezone()

        async def _action():
            callback_pipeline = None
            rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = \
                await getattr(
                    RedisChatRoomsByUserProfileS,
                    'zrevrange' if reverse else 'zrange')(await self.redis, user_profile_id)
            if not rooms_by_profile_redis:
                room_by_profile_db: List[ChatRoomUserAssociation] = await crud.list(
                    conditions=(ChatRoomUserAssociation.user_profile_id == user_profile_id,)
                )
                if room_by_profile_db:
                    async def _transaction(pipeline: Pipeline):
                        return await RedisChatRoomsByUserProfileS.zadd(
                            pipeline, user_profile_id, [
                                RedisChatRoomsByUserProfileS.schema(
                                    id=m.room_id, name=m.room_name, unread_msg_cnt=0, timestamp=now.timestamp()
                                ) for m in room_by_profile_db
                            ]
                        )

                    if not pipe:
                        async with await self.pipeline() as _pipe:
                            await (await _transaction(_pipe)).execute()
                    else:
                        callback_pipeline = await _transaction(pipe)

                elif raise_exception:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return rooms_by_profile_redis, callback_pipeline

        if lock:
            async with await self.lock(key=RedisChatRoomsByUserProfileS.get_lock_key(user_profile_id)):
                return await _action()
        return await _action()

    async def sync_room_by_user_profile(
        self,
        room_id: int,
        user_profile_id: int,
        crud: Optional[ChatRoomUserAssociationCRUD] = None,
        pipe: Optional[Pipeline] = None,
        lock=True, raise_exception=False
    ) -> Tuple[RedisChatRoomByUserProfileS, Pipeline | None]:
        now = datetime.now().astimezone()

        async def _action():
            callback_pipe = None
            rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = \
                await RedisChatRoomsByUserProfileS.zrevrange(await self.redis, user_profile_id)
            room_by_profile_redis: RedisChatRoomByUserProfileS = next(
                (r for r in rooms_by_profile_redis if r.id == room_id), None
            )
            if not room_by_profile_redis:
                room_by_profile_db: ChatRoomUserAssociation = await crud.get(
                    conditions=(
                        ChatRoomUserAssociation.room_id == room_id,
                        ChatRoomUserAssociation.user_profile_id == user_profile_id
                    )
                )
                if room_by_profile_db:
                    async def _transaction(pipeline: Pipeline):
                        return await RedisChatRoomsByUserProfileS.zadd(
                            pipeline, user_profile_id, RedisChatRoomsByUserProfileS.schema(
                                id=room_by_profile_db.room_id,
                                name=room_by_profile_db.room_name,
                                unread_msg_cnt=0,
                                timestamp=now.timestamp()
                            )
                        )

                    if not pipe:
                        async with await self.pipeline() as _pipe:
                            await (await _transaction(_pipe)).execute()
                    else:
                        callback_pipe = await _transaction(pipe)

                elif raise_exception:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return room_by_profile_redis, callback_pipe

        if lock:
            async with await self.lock(key=RedisChatRoomsByUserProfileS.get_lock_key(user_profile_id)):
                return await _action()
        return await _action()

    async def sync_user_profiles_in_room(
        self,
        room_id: int,
        user_profile_id: int,
        crud: Optional[ChatRoomUserAssociationCRUD] = None,
        pipe: Optional[Pipeline] = None,
        lock=True, raise_exception=False
    ) -> Tuple[List[RedisUserProfileByRoomS], Pipeline | None]:
        async def _action():
            callback_pipe = None
            profiles_by_room_redis: List[RedisUserProfileByRoomS] = \
                await RedisUserProfilesByRoomS.smembers(await self.redis, (room_id, user_profile_id))
            if not profiles_by_room_redis:
                room_user_mapping: List[ChatRoomUserAssociation] = \
                    await crud.list(
                        conditions=(
                            ChatRoomUserAssociation.room_id == room_id,),
                        options=[
                            joinedload(ChatRoomUserAssociation.user_profile)
                            .selectinload(UserProfile.images),
                            joinedload(ChatRoomUserAssociation.user_profile)
                            .selectinload(UserProfile.followers)
                        ]
                    )
                if room_user_mapping:
                    async def _transaction(pipeline: Pipeline):
                        return await RedisUserProfilesByRoomS.sadd(
                            pipeline, (room_id, user_profile_id), *[
                                RedisUserProfilesByRoomS.schema(
                                    id=p.user_profile.id,
                                    identity_id=p.user_profile.identity_id,
                                    nickname=p.user_profile.get_nickname_by_other(user_profile_id),
                                    files=await RedisUserImageFileS.generate_files_schema(
                                        p.user_profile.images
                                    )
                                ) for p in room_user_mapping
                            ]
                        )

                    if not pipe:
                        async with await self.pipeline() as _pipe:
                            await (await _transaction(_pipe)).execute()
                    else:
                        callback_pipe = await _transaction(pipe)

                elif raise_exception:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return profiles_by_room_redis, callback_pipe

        if lock:
            async with await self.lock(key=RedisUserProfilesByRoomS.get_lock_key((room_id, user_profile_id))):
                return await _action()
        return await _action()

    async def sync_user_profile_in_room(
        self,
        room_id: int,
        user_profile_id: int,
        crud: Optional[ChatRoomUserAssociationCRUD] = None,
        pipe: Optional[Pipeline] = None,
        lock=True, raise_exception=False,
    ) -> Tuple[RedisUserProfileByRoomS, Pipeline | None]:
        async def _action():
            callback_pipeline = None
            user_profiles_redis: List[RedisUserProfileByRoomS] = \
                await RedisUserProfilesByRoomS.smembers(await self.redis, (room_id, user_profile_id))
            user_profile_redis: RedisUserProfileByRoomS = next(
                (p for p in user_profiles_redis if p.id == user_profile_id), None
            )
            if not user_profile_redis:
                room_user_mapping: List[ChatRoomUserAssociation] = \
                    await crud.list(
                        conditions=(
                            ChatRoomUserAssociation.room_id == room_id,),
                        options=[
                            joinedload(ChatRoomUserAssociation.user_profile)
                            .selectinload(UserProfile.images),
                            joinedload(ChatRoomUserAssociation.user_profile)
                            .selectinload(UserProfile.followers)
                        ]
                    )
                if room_user_mapping:
                    m = next((m for m in room_user_mapping if m.user_profile_id == user_profile_id), None)
                    if m:
                        async def _transaction(pipeline: Pipeline):
                            return await RedisUserProfilesByRoomS.sadd(
                                pipeline, (room_id, user_profile_id), RedisUserProfilesByRoomS.schema(
                                    id=m.user_profile.id,
                                    identity_id=m.user_profile.identity_id,
                                    nickname=m.user_profile.get_nickname_by_other(user_profile_id),
                                    files=await RedisUserImageFileS.generate_files_schema(m.user_profile.images)
                                )
                            )

                        if not pipe:
                            async with await self.pipeline() as _pipe:
                                await (await _transaction(_pipe)).execute()
                        else:
                            callback_pipeline = await _transaction(pipe)

                elif raise_exception:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return user_profile_redis, callback_pipeline

        if lock:
            async with await self.lock(key=RedisUserProfilesByRoomS.get_lock_key((room_id, user_profile_id))):
                return await _action()
        return await _action()

    async def update_histories_by_room(
        self,
        room_id: int,
        histories: List[RedisChatHistoryByRoomS],
        pipe: Optional[Pipeline] = None
    ) -> Pipeline | None:
        async def _transaction(pipeline: Pipeline):
            pipeline = await RedisChatHistoriesByRoomS.zadd(pipeline, room_id, histories)
            sync_histories: List[RedisChatHistoryByRoomS] = [h for h in histories if h.id]
            if sync_histories:
                pipeline = await RedisChatHistoriesToSyncS.zadd(pipeline, room_id, sync_histories)
            return pipeline

        if not pipe:
            async with await self.pipeline() as p:
                await (await _transaction(p)).execute()
        else:
            return await _transaction(pipe)

    # 유저 채팅방 unread_msg_cnt 업데이트
    async def update_unread_msg_cnt(
        self,
        room_id: int,
        profile_id: int,
        crud: ChatRoomUserAssociationCRUD
    ):
        async with await self.lock(key=RedisChatRoomsByUserProfileS.get_lock_key(profile_id)):
            room_by_profile_redis, _ = await self.sync_room_by_user_profile(
                room_id, profile_id, crud, lock=False
            )
            if room_by_profile_redis:
                async with await self.pipeline() as pipe:
                    pipe = await RedisChatRoomsByUserProfileS.zrem(
                        pipe, profile_id, room_by_profile_redis
                    )
                    pipe = await RedisChatRoomsByUserProfileS.zadd(
                        pipe, profile_id, RedisChatRoomByUserProfileS(
                            id=room_by_profile_redis.id,
                            name=room_by_profile_redis.name,
                            unread_msg_cnt=room_by_profile_redis.unread_msg_cnt + 1,
                            timestamp=room_by_profile_redis.timestamp
                        )
                    )
                    await pipe.execute()

    async def init_unread_msg_cnt(
        self,
        user_profile_id: int,
        room: RedisChatRoomByUserProfileS
    ):
        async with await self.lock(
            key=RedisChatRoomsByUserProfileS.get_lock_key(user_profile_id)
        ):
            async with await self.pipeline() as pipe:
                pipe = await RedisChatRoomsByUserProfileS.zrem(pipe, user_profile_id, room)
                room.unread_msg_cnt = 0
                pipe = await RedisChatRoomsByUserProfileS.zadd(pipe, user_profile_id, room)
                await pipe.execute()

    async def connect_profile_by_room(
        self,
        user_profile_id: int,
        room_id: int,
        room: RedisChatRoomInfoS
    ):
        async with await self.lock(key=RedisInfoByRoomS.get_lock_key(room_id)):
            room.add_connected_profile_id(user_profile_id)
            await RedisInfoByRoomS.hset(
                await self.redis,
                room_id,
                field=RedisChatRoomInfoS.__fields__['connected_profile_ids'].name,
                value=room.connected_profile_ids
            )

    async def disconnect_profile_by_room(
        self,
        user_profile_id: int,
        room_id: int,
        room: RedisChatRoomInfoS
    ):
        async with await self.lock(key=RedisInfoByRoomS.get_lock_key(room_id)):
            room.connected_profile_ids = [
                profile_id for profile_id in room.connected_profile_ids
                if profile_id != user_profile_id
            ]
            await RedisInfoByRoomS.hset(
                await self.redis,
                room_id,
                field=RedisChatRoomInfoS.__fields__['connected_profile_ids'].name,
                value=room.connected_profile_ids
            )

    async def unsync_read_by_room(
        self,
        room_id: int,
        room: RedisChatRoomInfoS
    ) -> List[Tuple[RedisChatHistoryByRoomS, List[int]]]:
        # 최근 읽음 처리 동기화 안된 채팅 내역 추출
        chat_histories_redis: List[RedisChatHistoryByRoomS] = (
            await RedisChatHistoriesByRoomS.zrevrange(await self.redis, room_id)
        )
        unsync: List[Tuple[RedisChatHistoryByRoomS, List[int]]] = []
        for h in chat_histories_redis:
            if (
                len(set(h.read_user_ids) & set(room.connected_profile_ids))
                != len(room.connected_profile_ids)
            ):
                sync_read_user_ids = list(set(h.read_user_ids) | set(room.connected_profile_ids))
                unsync.append((h, sync_read_user_ids))
            else:
                break
        return unsync

    async def patch_unsync_read_by_room(
        self,
        room_id: int,
        room: RedisChatRoomInfoS
    ) -> List[RedisChatHistoryPatchS]:
        unsync_histories = await self.unsync_read_by_room(room_id, room)
        patch_histories_redis: List[RedisChatHistoryPatchS] = []
        if unsync_histories:
            async with await self.pipeline() as pipe:
                unsync, sync = [], []
                async for history, read_user_ids in async_iter(unsync_histories):
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

        return patch_histories_redis

    async def handle_pubsub(self, ws: WebSocket, producer_handler: Callable, consumer_handler: Callable):
        pub: Redis = await self.redis
        pubsub: PubSub = await self.pubsub()
        producer_task: Coroutine = producer_handler(pub=pub, ws=ws)
        consumer_task: Coroutine = consumer_handler(psub=pubsub, ws=ws)
        done, pending = await asyncio.wait(
            [producer_task, consumer_task], return_when=asyncio.FIRST_COMPLETED
        )
        if pending:
            for task in pending:
                task.cancel()


class WebSocketHandler:

    __slots__ = ('ws',)

    def __init__(self, ws: WebSocket):
        self.ws = ws

    def connect_ok(self):
        return self.ws.application_state in (WebSocketState.CONNECTING, WebSocketState.CONNECTED)

    def connected(self):
        return self.ws.application_state == WebSocketState.CONNECTED

    @classmethod
    def code_reason(cls, e: Exception):
        if isinstance(e, WebSocketDisconnect):
            code, reason = e.code, e.reason
        else:
            code, reason = status.WS_1011_INTERNAL_ERROR, ExceptionHandler(e).error
        return {'code': code, 'reason': reason}

    async def accept(
        self,
        sub_protocol: Optional[str] = None,
        headers: Optional[Iterable[Tuple[bytes, bytes]]] = None,
    ):
        await self.ws.accept(sub_protocol, headers)

    async def send_json(self, data: Any):
        if self.connect_ok():
            await self.ws.send_json(data)

    async def send_text(self, data: str):
        if self.connect_ok():
            await self.ws.send_text(data)

    async def receive_json(self, mode: str = 'text'):
        if self.connected:
            return await self.ws.receive_json(mode)

    async def close(
        self,
        code: Optional[int] = None,
        reason: Optional[str] = None,
        e: Optional[Exception] = None
    ):
        assert code or e, 'code or e must be provided.'
        if self.connect_ok():
            try:
                kwargs = {}
                if code:
                    kwargs['code'] = code
                    kwargs['reason'] = reason
                elif e:
                    kwargs = self.code_reason(e)
                await self.ws.close(**kwargs)
            except RuntimeError:
                pass

    @classmethod
    def self_disconnected(cls, e: Exception):
        return (
            isinstance(e, ConnectionClosedOK)
            or (
                isinstance(e, WebSocketDisconnect)
                and e.code in (status.WS_1000_NORMAL_CLOSURE, status.WS_1001_GOING_AWAY)
            )
        )
