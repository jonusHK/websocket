import asyncio
from datetime import datetime
from typing import Iterable, List, Dict, Any, Optional, Callable, Coroutine
from uuid import UUID

from aioredis import Redis
from aioredis.client import PubSub
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette import status
from starlette.websockets import WebSocket

from server.core.authentications import COOKIE_NAME, cookie, backend
from server.core.enums import IntValueEnum
from server.core.externals.redis.schemas import RedisChatRoomByUserProfileS, \
    RedisChatRoomsByUserProfileS, RedisUserProfilesByRoomS, RedisChatHistoriesByRoomS, RedisChatHistoriesToSyncS, \
    RedisUserImageFileS, RedisChatHistoryFileS, RedisUserProfileByRoomS, RedisChatHistoryByRoomS, RedisChatRoomInfoS, \
    RedisChatRoomsInfoS
from server.crud.service import ChatRoomCRUD, ChatRoomUserAssociationCRUD
from server.models import User, ChatRoomUserAssociation, UserProfile, UserProfileImage, \
    ChatHistoryFile, UserSession, ChatRoom


class AuthValidator:
    def __init__(self, session: AsyncSession):
        self.session = session

    @classmethod
    def validate_user_profile(cls, user_session: UserSession, user_profile_id):
        assert hasattr(user_session, 'user') and hasattr(user_session.user, 'profiles')
        if not next((p for p in user_session.user.profiles if p.id == user_profile_id and p.is_active), None):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

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
    def __init__(self, redis: Redis):
        self.redis = redis

    @classmethod
    async def generate_presigned_files(
        cls, model, iterable: Iterable
    ) -> List[RedisUserImageFileS | RedisChatHistoryFileS]:
        assert issubclass(model, UserProfileImage | ChatHistoryFile), 'Invalid model type.'

        model_schema_mapping = {
            UserProfileImage: RedisUserImageFileS,
            ChatHistoryFile: RedisChatHistoryFileS
        }
        schema = model_schema_mapping[model]

        files_s: List[schema] = []
        if iterable:
            urls: List[Dict[str, Any]] = [
                r.result() for r in await model.asynchronous_presigned_url(*iterable)
            ]
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
    async def generate_user_profile_images(
        cls,
        profiles: List[UserProfileImage],
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
        return await cls.generate_presigned_files(UserProfileImage, images)

    async def get_room(self, room_id: int, crud: Optional[ChatRoomCRUD] = None, sync=False) -> RedisChatRoomInfoS:
        while True:
            rooms_redis: List[RedisChatRoomInfoS] = await RedisChatRoomsInfoS.smembers(self.redis, None)
            room_redis: RedisChatRoomInfoS = next((r for r in rooms_redis if r.id == room_id), None)
            if not sync or room_redis:
                break
            room_db: ChatRoom = await crud.get(
                conditions=(ChatRoom.id == room_id,),
                options=[
                    selectinload(ChatRoom.user_profiles)
                    .joinedload(ChatRoomUserAssociation.user_profile)
                    .selectinload(UserProfile.images)
                ]
            )
            await RedisChatRoomsInfoS.sadd(self.redis, None, RedisChatRoomsInfoS.schema(
                id=room_db.id, type=room_db.type.name.lower(), user_cnt=len(room_db.user_profiles),
                user_profile_ids=[m.user_profile_id for m in room_db.user_profiles],
                user_profile_files=await self.generate_user_profile_images(
                    [m.user_profile for m in room_db.user_profiles], only_default=True
                ), is_active=room_db.is_active
            ))

    async def get_rooms_by_user_profile(
        self, user_profile_id: int, crud: Optional[ChatRoomUserAssociationCRUD] = None, reverse=False, sync=False
    ) -> List[RedisChatRoomByUserProfileS]:
        now = datetime.now().astimezone()
        while True:
            rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = \
                await getattr(
                    RedisChatRoomsByUserProfileS,
                    'zrevrange' if reverse else 'zrange')(self.redis, user_profile_id)
            if not sync or rooms_by_profile_redis:
                break
            room_by_profile_db: List[ChatRoomUserAssociation] = await crud.list(
                conditions=(ChatRoomUserAssociation.user_profile_id == user_profile_id,))
            if not room_by_profile_db:
                break
            await RedisChatRoomsByUserProfileS.zadd(self.redis, user_profile_id, *[
                RedisChatRoomsByUserProfileS.schema(
                    id=m.room_id, name=m.room_name, unread_msg_cnt=0, timestamp=now.timestamp()
                ) for m in room_by_profile_db
            ])
        return rooms_by_profile_redis

    async def get_room_by_user_profile(
        self, room_id: int, user_profile_id: int, crud: Optional[ChatRoomCRUD] = None, sync=False
    ) -> RedisChatRoomByUserProfileS:
        now = datetime.now().astimezone()
        while True:
            rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = \
                await RedisChatRoomsByUserProfileS.zrange(self.redis, user_profile_id)
            room_by_profile_redis: RedisChatRoomByUserProfileS = next((
                r for r in rooms_by_profile_redis if r.id == room_id), None) if rooms_by_profile_redis else None
            if not sync or room_by_profile_redis:
                break
            room_by_profile_db: ChatRoomUserAssociation = await crud.get(
                conditions=(
                    ChatRoomUserAssociation.room_id == room_id,
                    ChatRoomUserAssociation.user_profile_id == user_profile_id))
            await RedisChatRoomsByUserProfileS.zadd(self.redis, user_profile_id, RedisChatRoomsByUserProfileS.schema(
                id=room_by_profile_db.room_id,
                name=room_by_profile_db.room_name,
                unread_msg_cnt=0,
                timestamp=now.timestamp()))

        return room_by_profile_redis

    async def get_user_profiles_in_room(
        self, room_id: int, user_profile_id: int, crud: Optional[ChatRoomUserAssociationCRUD] = None, sync=False
    ) -> List[RedisUserProfileByRoomS]:
        while True:
            user_profiles_redis: List[RedisUserProfileByRoomS] = \
                await RedisUserProfilesByRoomS.smembers(self.redis, (room_id, user_profile_id))
            if not sync or user_profiles_redis:
                break
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
            if not room_user_mapping:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not exist any user in the room.')
            await RedisUserProfilesByRoomS.sadd(self.redis, (room_id, user_profile_id), *[
                RedisUserProfilesByRoomS.schema(
                    id=p.user_profile.id,
                    identity_id=p.user_profile.identity_id,
                    nickname=p.user_profile.get_nickname_by_other(user_profile_id),
                    files=await self.generate_presigned_files(
                        UserProfileImage, p.user_profile.images)
                ) for p in room_user_mapping])

        return user_profiles_redis

    async def get_user_profile_in_room(
        self, room_id: int, user_profile_id: int, crud: Optional[ChatRoomUserAssociationCRUD] = None, sync=False
    ) -> RedisUserProfileByRoomS:
        while True:
            user_profiles_redis: List[RedisUserProfileByRoomS] = \
                await RedisUserProfilesByRoomS.smembers(self.redis, (room_id, user_profile_id))
            user_profile_redis: RedisUserProfileByRoomS = next((
                p for p in user_profiles_redis if p.id == user_profile_id), None) if user_profiles_redis else None
            if not sync or user_profile_redis:
                break
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
            if not room_user_mapping:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not exist any user in the room.')
            m = next((m for m in room_user_mapping if m.user_profile_id == user_profile_id), None)
            if m:
                await RedisUserProfilesByRoomS.sadd(
                    self.redis, (room_id, user_profile_id), RedisUserProfilesByRoomS.schema(
                        id=m.user_profile.id,
                        identity_id=m.user_profile.identity_id,
                        nickname=m.user_profile.get_nickname_by_other(user_profile_id),
                        files=await self.generate_presigned_files(UserProfileImage, m.user_profile.images)))

        return user_profile_redis

    async def update_histories_by_room(self, room_id: int, histories: List[RedisChatHistoryByRoomS]):
        await RedisChatHistoriesByRoomS.zadd(self.redis, room_id, histories)
        await RedisChatHistoriesToSyncS.zadd(self.redis, room_id, [
            RedisChatHistoriesToSyncS.schema(id=history.id) for history in histories
        ])

    async def handle_pubsub(self, ws: WebSocket, producer_handler: Callable, consumer_handler: Callable, logger):
        pubsub: PubSub = self.redis.pubsub()
        producer_task: Coroutine = producer_handler(pub=self.redis, ws=ws)
        consumer_task: Coroutine = consumer_handler(psub=pubsub, ws=ws)
        done, pending = await asyncio.wait(
            [producer_task, consumer_task], return_when=asyncio.FIRST_COMPLETED)
        logger.info(f"Done task: {done}")
        for task in pending:
            logger.info(f"Canceling task: {task}")
            task.cancel()


def generate_room_mapping_name(user_profile_id: int, other_profiles: List[UserProfile]):
    return ', '.join([p.get_nickname_by_other(user_profile_id) for p in other_profiles])
