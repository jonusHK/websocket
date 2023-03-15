import uuid
from datetime import datetime
from typing import List

from server.api.common import AsyncRedisHandler
from server.api.websocket.chat import ChatHandler
from server.core.enums import SendMessageType, ChatHistoryType
from server.core.externals.redis.schemas import RedisChatHistoryByRoomS, RedisChatHistoriesByRoomS, RedisChatRoomInfoS, \
    RedisUserProfileByRoomS
from server.crud.service import ChatRoomUserAssociationCRUD


class MessageHandler(ChatHandler):

    send_type = SendMessageType.MULTICAST

    async def handle(self, **kwargs):
        crud_room_user_mapping = ChatRoomUserAssociationCRUD(self.session)

        redis_handler: AsyncRedisHandler = kwargs.get('redis_handler')
        user_profile_id: int = kwargs.get('user_profile_id')
        room_id: int = kwargs.get('room_id')
        room_redis: RedisChatRoomInfoS = kwargs.get('room_redis')
        user_profiles_redis: List[RedisUserProfileByRoomS] = kwargs.get('user_profiles_redis')
        now: datetime = datetime.now().astimezone()

        # Redis 저장
        chat_history_redis: RedisChatHistoryByRoomS = RedisChatHistoryByRoomS(
            redis_id=uuid.uuid4().hex,
            user_profile_id=user_profile_id,
            contents=self.receive.data.text,
            type=ChatHistoryType.MESSAGE.name.lower(),
            read_user_ids=list({user_profile_id} | set(room_redis.connected_profile_ids)),
            timestamp=now.timestamp(),
            date=now.date().isoformat(),
            is_active=True
        )
        await RedisChatHistoriesByRoomS.zadd(await redis_handler.redis, room_id, chat_history_redis)

        # 각 유저 별 해당 방의 unread_msg_cnt 업데이트
        for p in user_profiles_redis:
            if p.id not in room_redis.connected_profile_ids:
                await redis_handler.update_unread_msg_cnt(
                    room_id,
                    p.id,
                    crud_room_user_mapping
                )

        self._result = chat_history_redis
        return self._result

    @property
    def send_kwargs(self):
        assert self._result is not None, 'Run `handle()` first.'
        return dict(
            history=self._result
        )
