import asyncio
from datetime import datetime
from typing import Iterable, List, Dict, Any, Optional, Callable, Coroutine, Tuple
from uuid import UUID

from aioredis.client import Pipeline, Redis, PubSub
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette import status
from starlette.websockets import WebSocket
from websockets.exceptions import WebSocketException

from server.core.authentications import COOKIE_NAME, cookie, backend
from server.core.enums import IntValueEnum
from server.core.externals.redis import AioRedis
from server.core.externals.redis.schemas import (
    RedisChatRoomByUserProfileS, RedisChatRoomsByUserProfileS, RedisUserProfilesByRoomS,
    RedisChatHistoriesByRoomS, RedisChatHistoriesToSyncS, RedisUserImageFileS,
    RedisChatHistoryFileS, RedisUserProfileByRoomS, RedisChatHistoryByRoomS, RedisInfoByRoomS,
    RedisChatRoomInfoS
)
from server.crud.service import ChatRoomCRUD, ChatRoomUserAssociationCRUD
from server.models import (
    User, ChatRoomUserAssociation, UserProfile, UserProfileImage,
    ChatHistoryFile, UserSession, ChatRoom
)


class AuthValidator:
    def __init__(self, session: AsyncSession):
        self.session = session

    @classmethod
    def get_user_profile(cls, user_session: UserSession, user_profile_id):
        assert hasattr(user_session, 'user') and hasattr(user_session.user, 'profiles')
        profile: UserProfile = next((
            p for p in user_session.user.profiles if p.id == user_profile_id and p.is_active),
            None
        )
        if not profile:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return profile

    async def get_user_by_websocket(self, websocket: WebSocket) -> User:
        signed_session_id = websocket.cookies[COOKIE_NAME]
        session_id = UUID(
            cookie.signer.loads(
                signed_session_id,
                max_age=cookie.cookie_params.max_age,
                return_timestamp=False,
            )
        )
        user_session = await backend.read(session_id, self.session)
        user = user_session.user
        return user


class RedisHandler:

    def __init__(self, redis: Optional[Redis] = None, **kwargs):
        if redis is None:
            redis = AioRedis(**kwargs).redis
        self.redis = redis
        self.pipeline = self.redis.pipeline

    def lock(self, key: str, timeout: int = 5):
        return self.redis.lock(name=key, timeout=timeout)

    @classmethod
    async def generate_files_schema(
        cls,
        model,
        iterable: Iterable,
        presigned=False
    ) -> List[RedisUserImageFileS | RedisChatHistoryFileS]:
        assert issubclass(model, UserProfileImage | ChatHistoryFile), 'Invalid model type.'

        model_schema_mapper = {
            UserProfileImage: RedisUserImageFileS,
            ChatHistoryFile: RedisChatHistoryFileS
        }
        schema = model_schema_mapper[model]

        files_s: List[schema] = []
        if iterable:
            urls: List[Dict[str, Any]] = (
                await model.asynchronous_presigned_url(*iterable)
                if presigned
                else model.get_file_urls(*iterable)
            )
            for m in iterable:
                model_to_dict = m.to_dict()
                model_to_dict.update({
                    'url': next((u['url'] for u in urls if u['id'] == m.id), None)
                })

                for k, v in schema.__annotations__.items():
                    if type(model_to_dict[k]) is not v:
                        if isinstance(model_to_dict[k], IntValueEnum):
                            if v is str:
                                model_to_dict[k] = model_to_dict[k].name.lower()
                            elif v is int:
                                model_to_dict[k] = model_to_dict[k].value
                files_s.append(schema(**model_to_dict))

        return files_s

    @classmethod
    async def generate_profile_images_schema(
        cls,
        profiles: List[UserProfile],
        only_default=False
    ) -> List[RedisUserImageFileS]:
        images: List[UserProfileImage] = []
        for p in profiles:
            assert hasattr(p, 'images'), 'Profile must have `images` attr.'
            if only_default:
                image = next((im for im in p.images if im.is_default), None)
                if image:
                    images.append(image)
            else:
                for image in p.images:
                    images.append(image)
        return await cls.generate_files_schema(UserProfileImage, images)

    async def generate_default_room_name(
        self,
        room_id: int,
        user_profile_id: int,
        profiles_by_room_redis: List[RedisUserProfileByRoomS] = None
    ) -> str | None:
        profiles_by_room_redis: List[RedisUserProfileByRoomS] = (
            profiles_by_room_redis
            or await RedisUserProfilesByRoomS.smembers(
                self.redis, (room_id, user_profile_id)
            )
        )
        if not profiles_by_room_redis:
            return
        profiles_by_room_redis.sort(key=lambda x: x.nickname)
        if len(profiles_by_room_redis) == 2:
            room_name = next(
                (p.nickname for p in profiles_by_room_redis if p.id != user_profile_id),
                None
            )
        else:
            room_name: str = ', '.join([p.nickname for p in profiles_by_room_redis])
        return room_name

    async def get_room(
        self,
        room_id: int,
        crud: Optional[ChatRoomCRUD] = None,
        pipe: Optional[Pipeline] = None,
        sync=False, lock=True, raise_exception=False
    ) -> Tuple[RedisChatRoomInfoS, Pipeline | None]:
        async def _action():
            callback_pipe = None
            room_redis: RedisChatRoomInfoS = await RedisInfoByRoomS.hgetall(self.redis, room_id)
            if not room_redis and sync:
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
                                user_profile_files=await self.generate_profile_images_schema(
                                    [m.user_profile for m in room_db.user_profiles], only_default=True
                                ), connected_profile_ids=[]
                            )
                        )

                    if not pipe:
                        async with self.pipeline() as _pipe:
                            await (await _transaction(_pipe)).execute()
                    else:
                        callback_pipe = await _transaction(pipe)

                elif raise_exception:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return room_redis, callback_pipe

        if lock:
            async with self.lock(key=RedisInfoByRoomS.get_lock_key()):
                return await _action()
        return await _action()

    async def get_rooms_by_user_profile(
        self,
        user_profile_id: int,
        crud: Optional[ChatRoomUserAssociationCRUD] = None,
        pipe: Optional[Pipeline] = None,
        reverse=False, sync=False, lock=True, raise_exception=False
    ) -> Tuple[List[RedisChatRoomByUserProfileS], Pipeline | None]:
        now = datetime.now().astimezone()

        async def _action():
            callback_pipeline = None
            rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = \
                await getattr(
                    RedisChatRoomsByUserProfileS,
                    'zrevrange' if reverse else 'zrange')(self.redis, user_profile_id)
            if not rooms_by_profile_redis and sync:
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
                        async with self.pipeline() as _pipe:
                            await (await _transaction(_pipe)).execute()
                    else:
                        callback_pipeline = await _transaction(pipe)

                elif raise_exception:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return rooms_by_profile_redis, callback_pipeline

        if lock:
            async with self.lock(key=RedisChatRoomsByUserProfileS.get_lock_key(user_profile_id)):
                return await _action()
        return await _action()

    async def get_room_by_user_profile(
        self,
        room_id: int,
        user_profile_id: int,
        crud: Optional[ChatRoomUserAssociationCRUD] = None,
        pipe: Optional[Pipeline] = None,
        sync=False, lock=True, raise_exception=False
    ) -> Tuple[RedisChatRoomByUserProfileS, Pipeline | None]:
        now = datetime.now().astimezone()

        async def _action():
            callback_pipe = None
            rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = \
                await RedisChatRoomsByUserProfileS.zrevrange(self.redis, user_profile_id)
            room_by_profile_redis: RedisChatRoomByUserProfileS = next(
                (r for r in rooms_by_profile_redis if r.id == room_id), None
            )
            if not room_by_profile_redis and sync:
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
                        async with self.pipeline() as _pipe:
                            await (await _transaction(_pipe)).execute()
                    else:
                        callback_pipe = await _transaction(pipe)

                elif raise_exception:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return room_by_profile_redis, callback_pipe

        if lock:
            async with self.lock(key=RedisChatRoomsByUserProfileS.get_lock_key(user_profile_id)):
                return await _action()
        return await _action()

    async def get_user_profiles_in_room(
        self,
        room_id: int,
        user_profile_id: int,
        crud: Optional[ChatRoomUserAssociationCRUD] = None,
        pipe: Optional[Pipeline] = None,
        sync=False, lock=True, raise_exception=False
    ) -> Tuple[List[RedisUserProfileByRoomS], Pipeline | None]:
        async def _action():
            callback_pipe = None
            profiles_by_room_redis: List[RedisUserProfileByRoomS] = \
                await RedisUserProfilesByRoomS.smembers(self.redis, (room_id, user_profile_id))
            if not profiles_by_room_redis and sync:
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
                                    files=await self.generate_files_schema(
                                        UserProfileImage, p.user_profile.images
                                    )
                                ) for p in room_user_mapping
                            ]
                        )

                    if not pipe:
                        async with self.pipeline() as _pipe:
                            await (await _transaction(_pipe)).execute()
                    else:
                        callback_pipe = await _transaction(pipe)

                elif raise_exception:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return profiles_by_room_redis, callback_pipe

        if lock:
            async with self.lock(key=RedisUserProfilesByRoomS.get_lock_key((room_id, user_profile_id))):
                return await _action()
        return await _action()

    async def get_user_profile_in_room(
        self,
        room_id: int,
        user_profile_id: int,
        crud: Optional[ChatRoomUserAssociationCRUD] = None,
        pipe: Optional[Pipeline] = None,
        sync=False, lock=True, raise_exception=False,
    ) -> Tuple[RedisUserProfileByRoomS, Pipeline | None]:
        async def _action():
            callback_pipeline = None
            user_profiles_redis: List[RedisUserProfileByRoomS] = \
                await RedisUserProfilesByRoomS.smembers(self.redis, (room_id, user_profile_id))
            user_profile_redis: RedisUserProfileByRoomS = next(
                (p for p in user_profiles_redis if p.id == user_profile_id), None
            )
            if not user_profile_redis and sync:
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
                                    files=await self.generate_files_schema(UserProfileImage, m.user_profile.images)
                                )
                            )

                        if not pipe:
                            async with self.pipeline() as _pipe:
                                await (await _transaction(_pipe)).execute()
                        else:
                            callback_pipeline = await _transaction(pipe)

                elif raise_exception:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return user_profile_redis, callback_pipeline

        if lock:
            async with self.lock(key=RedisUserProfilesByRoomS.get_lock_key((room_id, user_profile_id))):
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
            async with self.pipeline() as p:
                await (await _transaction(p)).execute()
        else:
            return await _transaction(pipe)

    # 유저 채팅방 unread_msg_cnt 업데이트
    async def update_unread_msg_cnt(
        self,
        room_id: int,
        profile_id: int,
        crud: ChatRoomUserAssociationCRUD,
        timestamp: Optional[float] = None
    ):
        async with self.lock(key=RedisChatRoomsByUserProfileS.get_lock_key(profile_id)):
            room_by_profile_redis, _ = await self.get_room_by_user_profile(
                room_id, profile_id, crud, sync=True, lock=False
            )
            if room_by_profile_redis:
                async with self.pipeline() as pipe:
                    pipe = await RedisChatRoomsByUserProfileS.zrem(
                        pipe, profile_id, room_by_profile_redis
                    )
                    pipe = await RedisChatRoomsByUserProfileS.zadd(
                        pipe, profile_id, RedisChatRoomByUserProfileS(
                            id=room_by_profile_redis.id,
                            name=room_by_profile_redis.name,
                            unread_msg_cnt=room_by_profile_redis.unread_msg_cnt + 1,
                            timestamp=timestamp or datetime.now().astimezone().timestamp()
                        )
                    )
                    await pipe.execute()

    async def handle_pubsub(self, ws: WebSocket, producer_handler: Callable, consumer_handler: Callable, logger):
        pubsub: PubSub = self.redis.pubsub()
        producer_task: Coroutine = producer_handler(pub=self.redis, ws=ws)
        consumer_task: Coroutine = consumer_handler(psub=pubsub, ws=ws)
        done, pending = await asyncio.wait(
            [producer_task, consumer_task], return_when=asyncio.FIRST_COMPLETED
        )
        logger.info(f"Done task: {done}")
        if pending:
            for task in pending:
                logger.info(f"Canceling task: {task}")
                task.cancel()
            raise WebSocketException('Cancelled task.')


def generate_room_mapping_name(user_profile_id: int, other_profiles: List[UserProfile]):
    return ', '.join([p.get_nickname_by_other(user_profile_id) for p in other_profiles])
