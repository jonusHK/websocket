from typing import Iterable, List, Dict, Any, Optional
from uuid import UUID

from aioredis import Redis
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from starlette import status
from starlette.websockets import WebSocket

from server.core.authentications import COOKIE_NAME, cookie, backend
from server.core.enums import IntValueEnum
from server.core.externals.redis.schemas import RedisChatRoomByUserProfileS, \
    RedisChatRoomsByUserProfileS, RedisUserProfilesByRoomS, RedisChatHistoriesByRoomS, RedisChatHistoriesToSyncS, \
    RedisUserImageFileS, RedisChatHistoryFileS, RedisUserProfileByRoomS, RedisChatHistoryByRoomS
from server.crud.service import ChatRoomCRUD, ChatRoomUserAssociationCRUD
from server.models import User, ChatRoom, ChatRoomUserAssociation, UserProfile, UserProfileImage, \
    ChatHistoryFile


class AuthValidator:
    def __init__(self, session: AsyncSession):
        self.session = session

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
    async def generate_presigned_files(cls, model, iterable: Iterable):
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
                                model_to_dict[k] = model_to_dict[k].name
                            elif v is int:
                                model_to_dict[k] = model_to_dict[k].value
                files_s.append(schema(**model_to_dict))

        return files_s

    async def get_room_with_user_profile(
        self, room_id: int, user_profile_id: int, crud: Optional[ChatRoomCRUD] = None, sync=False
    ) -> RedisChatRoomByUserProfileS:
        while True:
            rooms_redis: List[RedisChatRoomByUserProfileS] = \
                await RedisChatRoomsByUserProfileS.smembers(self.redis, user_profile_id)
            room_redis: RedisChatRoomByUserProfileS = next((
                r for r in rooms_redis if r.id == room_id), None) if rooms_redis else None
            if not sync:
                break
            if room_redis:
                break
            room_db: ChatRoom = await crud.get(
                conditions=(ChatRoom.id == room_id, ChatRoom.is_active == 1),
                options=[
                    selectinload(ChatRoom.user_profiles)
                    .joinedload(ChatRoomUserAssociation.user_profile)
                    .selectinload(UserProfile.images),
                    joinedload(ChatRoomUserAssociation.room)
                ]
            )
            if (
                not room_db.user_profiles
                or not next((m for m in room_db.user_profiles if m.user_profile_id != user_profile_id), None)
            ):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No users for room')
            await RedisChatRoomsByUserProfileS.sadd(self.redis, user_profile_id, *[
                RedisChatRoomsByUserProfileS.schema(
                    id=m.room_id,
                    name=m.room.get_name_by_user_profile(user_profile_id),
                    type=m.room.type,
                    user_profile_files=await self.generate_presigned_files(UserProfileImage, m.user_profile.images),
                    unread_msg_cnt=0) for m in room_db.user_profiles])

        return room_redis

    async def get_user_profiles_in_room(
        self, room_id: int, user_profile_id: int, crud: Optional[ChatRoomUserAssociationCRUD] = None, sync=False
    ) -> List[RedisUserProfileByRoomS]:
        while True:
            user_profiles_redis: List[RedisUserProfileByRoomS] = \
                await RedisUserProfilesByRoomS.smembers(self.redis, (room_id, user_profile_id))
            if not sync:
                break
            if user_profiles_redis:
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
                    nickname=p.user_profile.get_nickname_by_other(user_profile_id),
                    files=await self.generate_presigned_files(
                        UserProfileImage, p.user_profile.images)
                ) for p in room_user_mapping])

        return user_profiles_redis

    async def update_histories_by_room(self, room_id: int, histories: List[RedisChatHistoryByRoomS]):
        await RedisChatHistoriesByRoomS.zadd(self.redis, room_id, histories)
        await RedisChatHistoriesToSyncS.zadd(self.redis, room_id, [
            RedisChatHistoriesToSyncS.schema(id=history.id) for history in histories
        ])
