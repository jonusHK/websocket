from copy import deepcopy
from typing import List, Dict, Any

from sqlalchemy.orm import selectinload

from server.api.websocket.chat import ChatHandler
from server.core.enums import SendMessageType
from server.core.externals.redis.schemas import RedisChatHistoryPatchS, RedisChatHistoryByRoomS, \
    RedisChatHistoriesByRoomS
from server.crud.service import ChatHistoryCRUD
from server.models import ChatHistory


class PatchHandler(ChatHandler):

    send_type = SendMessageType.MULTICAST

    async def handle(self, **kwargs):
        crud_chat_history = ChatHistoryCRUD(self.session)

        redis_handler = kwargs.get('redis_handler')
        room_id = kwargs.get('room_id')

        if not self.receive.data.history_redis_ids:
            self.logger.warning("Not exists chat history redis ids.")
            return

        patch_histories_redis: List[RedisChatHistoryPatchS] = []

        # 업데이트 필요한 필드 확인
        update_fields = (ChatHistory.is_active.name,)
        update_target_redis: List[RedisChatHistoryByRoomS] = []
        update_target_db: List[str] = []
        update_values_db: Dict[str, Any] = {}

        async with await redis_handler.lock(key=RedisChatHistoriesByRoomS.get_lock_key(room_id)):
            chat_histories_redis: List[RedisChatHistoryByRoomS] = (
                await RedisChatHistoriesByRoomS.zrevrange(await redis_handler.redis, room_id)
            )
            if not chat_histories_redis:
                self.logger.warning("Not exists chat histories in the room. room_id: %s", room_id)
                return

            async with await redis_handler.pipeline() as pipe:
                for redis_id in self.receive.data.history_redis_ids:
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
                        if getattr(self.receive.data, f) is None:
                            continue
                        if duplicated_histories_redis:
                            # 기존 데이터와 다른 경우 업데이트 설정
                            if getattr(self.receive.data, f) != getattr(
                                    duplicated_histories_redis[0], f
                            ):
                                setattr(copied_history_redis, f, getattr(self.receive.data, f))
                                update_redis = True
                        else:
                            update_values_db.update({f: getattr(self.receive.data, f)})
                    if update_redis:
                        update_target_redis.append(copied_history_redis)
                        pipe = await RedisChatHistoriesByRoomS.zrem(
                            pipe, room_id, *duplicated_histories_redis
                        )
                    if update_values_db:
                        update_target_db.append(redis_id)
                # Redis 에 저장되어 있는 데이터 업데이트
                if update_target_redis:
                    pipe = await redis_handler.update_histories_by_room(
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
            await self.session.commit()
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

        self._result = patch_histories_redis
        return self._result

    @property
    def send_kwargs(self):
        assert self._result is not None, 'Run `handle()` first.'
        return dict(
            patch_histories=self._result
        )
