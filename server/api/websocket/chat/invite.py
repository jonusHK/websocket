import uuid
from datetime import datetime
from typing import List, Set

from sqlalchemy.orm import selectinload, joinedload

from server.api.websocket.chat import ChatHandler
from server.core.enums import SendMessageType, ChatHistoryType
from server.core.externals.redis.schemas import RedisChatHistoriesByRoomS, RedisChatHistoryByRoomS, \
    RedisChatRoomsByUserProfileS, RedisChatRoomByUserProfileS, RedisUserProfilesByRoomS, RedisInfoByRoomS, \
    RedisUserImageFileS, RedisUserProfileByRoomS
from server.crud.service import ChatRoomUserAssociationCRUD
from server.crud.user import UserProfileCRUD
from server.models import UserProfile, ChatRoomUserAssociation


class InviteHandler(ChatHandler):

    send_type = SendMessageType.MULTICAST

    async def handle(self, **kwargs):
        crud_room_user_mapping = ChatRoomUserAssociationCRUD(self.session)
        crud_user_profile = UserProfileCRUD(self.session)

        redis_handler = kwargs.get('redis_handler')
        user_profile_id = kwargs.get('user_profile_id')
        user_profile_redis = kwargs.get('user_profile_redis')
        room_id = kwargs.get('room_id')
        room_redis = kwargs.get('room_redis')
        now = datetime.now().astimezone()

        target_profile_ids: List[int] = self.receive.data.target_profile_ids
        if not target_profile_ids:
            return

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
            await RedisUserImageFileS.generate_profile_images_schema(
                current_profiles, only_default=True
            )
        )
        current_profile_ids: Set[int] = {p.id for p in current_profiles}
        for current_id in current_profile_ids:
            async with await redis_handler.lock(
                    key=RedisUserProfilesByRoomS.get_lock_key((room_id, current_id))
            ):
                _user_profiles_redis: List[RedisUserProfileByRoomS] = (
                    await RedisUserProfilesByRoomS.smembers(
                        await redis_handler.redis, (room_id, current_id)
                    )
                )
                if len(_user_profiles_redis) != len(_room_user_mapping):
                    async with await redis_handler.pipeline() as pipe:
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
            return
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
        await self.session.commit()

        total_profiles: List[UserProfile] = current_profiles + profiles
        profile_images_redis: List[RedisUserImageFileS] = (
            await RedisUserImageFileS.generate_profile_images_schema(profiles, only_default=True)
        )
        total_profile_images_redis: List[RedisUserImageFileS] = (
                current_profile_images_redis + profile_images_redis
        )

        # 방 정보 업데이트
        async with await redis_handler.lock(key=RedisInfoByRoomS.get_lock_key()):
            async with await redis_handler.pipeline() as pipe:
                room_redis.user_profile_ids = [p.id for p in total_profiles]
                room_redis.user_profile_files = total_profile_images_redis
                await RedisInfoByRoomS.hset(await redis_handler.redis, room_id, data=room_redis)
                await pipe.execute()

        for target_profile in total_profiles:
            # 각 방에 있는 유저 기준으로 데이터 업데이트
            async with await redis_handler.lock(
                    key=RedisUserProfilesByRoomS.get_lock_key((room_id, target_profile.id))
            ):
                await RedisUserProfilesByRoomS.sadd(
                    await redis_handler.redis, (room_id, target_profile.id), *[
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
            async with await redis_handler.lock(
                    key=RedisChatRoomsByUserProfileS.get_lock_key(target_profile.id)
            ):
                _room_by_profile_redis = await RedisChatRoomsByUserProfileS.zrevrange(
                    await redis_handler.redis, user_profile_id
                )
                if not _room_by_profile_redis:
                    await RedisChatRoomsByUserProfileS.zadd(
                        await redis_handler.redis, target_profile.id, RedisChatRoomByUserProfileS(
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
        await RedisChatHistoriesByRoomS.zadd(await redis_handler.redis, room_id, chat_history_redis)

        self._result = chat_history_redis
        return self._result

    @property
    def send_kwargs(self):
        assert self._result is not None, 'Run `handle()` first.'
        return dict(
            history=self._result
        )