import uuid
from datetime import datetime
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import joinedload
from starlette import status

from server.api.common import AsyncRedisHandler, WebSocketHandler
from server.api.websocket.chat import ChatHandler
from server.core.enums import SendMessageType, ChatHistoryType
from server.core.externals.redis.schemas import RedisUserProfilesByRoomS, RedisChatRoomsByUserProfileS, \
    RedisChatRoomByUserProfileS, RedisUserProfileByRoomS, RedisInfoByRoomS, RedisChatHistoryByRoomS, \
    RedisChatHistoriesByRoomS, RedisChatRoomInfoS
from server.crud.service import ChatRoomUserAssociationCRUD
from server.models import ChatRoomUserAssociation, ChatRoom


class TerminateHandler(ChatHandler):

    send_type = SendMessageType.MULTICAST

    async def handle(self, **kwargs):
        crud_room_user_mapping = ChatRoomUserAssociationCRUD(self.session)

        redis_handler: AsyncRedisHandler = kwargs.get('redis_handler')
        ws_handler: WebSocketHandler = kwargs.get('ws_handler')
        user_profile_id: int = kwargs.get('user_profile_id')
        room_id: int = kwargs.get('room_id')
        room_redis: RedisChatRoomInfoS = kwargs.get('room_redis')
        user_profile_redis: RedisUserProfileByRoomS = kwargs.get('user_profile_redis')
        now: datetime = datetime.now().astimezone()

        room_db: ChatRoom | None = None
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
            async with await redis_handler.pipeline() as pipe:
                rooms_by_profile_redis: List[RedisChatRoomByUserProfileS] = (
                    await RedisChatRoomsByUserProfileS.zrange(await redis_handler.redis, user_profile_id)
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
                        async with await redis_handler.lock(
                                key=RedisUserProfilesByRoomS.get_lock_key((room_id, profile_id))
                        ):
                            profiles_redis: List[RedisUserProfileByRoomS] = (
                                await RedisUserProfilesByRoomS.smembers(
                                    await redis_handler.redis, (room_id, profile_id)
                                )
                            )
                            remove_profile_redis: List[RedisUserProfileByRoomS] = [
                                p for p in profiles_redis if p.id == user_profile_id
                            ]
                            pipe = await RedisUserProfilesByRoomS.srem(
                                pipe, (room_id, profile_id), *remove_profile_redis
                            )

                async with await redis_handler.lock(key=RedisInfoByRoomS.get_lock_key()):
                    if room_db and not room_db.is_active:
                        await RedisInfoByRoomS.delete(await redis_handler.redis, room_id)
                    else:
                        room_redis.user_profile_ids = [
                            i for i in room_redis.user_profile_ids if i != user_profile_id
                        ]
                        room_redis.user_profile_files = [
                            f for f in room_redis.user_profile_files
                            if f.user_profile_id != user_profile_id
                        ]
                        await RedisInfoByRoomS.hset(await redis_handler.redis, room_id, data=room_redis)

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
                    await redis_handler.redis, room_id, chat_history_redis
                )

                await self.session.commit()
                await pipe.execute()
                await ws_handler.close(code=status.WS_1001_GOING_AWAY, reason='Self terminated.')

                self._result = chat_history_redis
                return self._result

    @property
    def send_kwargs(self):
        assert self._result is not None, 'Run `handle()` first.'
        return dict(
            history=self._result
        )
