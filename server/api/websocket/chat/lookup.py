from typing import List

from sqlalchemy.orm import selectinload, joinedload

from server.api.websocket.chat import ChatHandler
from server.core.enums import SendMessageType
from server.core.externals.redis.schemas import RedisChatHistoryByRoomS, RedisChatHistoriesByRoomS
from server.crud.service import ChatHistoryCRUD, ChatHistoryUserAssociationCRUD
from server.models import ChatHistory, UserProfile, ChatHistoryUserAssociation


class LookUpHandler(ChatHandler):

    send_type = SendMessageType.UNICAST

    async def handle(self, **kwargs):
        crud_chat_history = ChatHistoryCRUD(self.session)
        crud_history_user_mapping = ChatHistoryUserAssociationCRUD(self.session)

        redis_handler = kwargs.get('redis_handler')
        user_profile_id = kwargs.get('user_profile_id')
        room_id = kwargs.get('room_id')

        if self.receive.data.offset is None or self.receive.data.limit is None:
            self.logger.warning("Not exists offset or limit for page.")
            return

        # Redis 대화 내용 조회
        chat_histories_redis: List[RedisChatHistoryByRoomS] = (
            await RedisChatHistoriesByRoomS.zrevrange(
                await redis_handler.redis, room_id,
                start=self.receive.data.offset,
                end=self.receive.data.offset + self.receive.data.limit - 1
            )
        )
        # Redis 데이터 없는 경우 DB 조회
        lack_cnt: int = self.receive.data.limit - len(chat_histories_redis)
        migrated_chat_histories_redis: List[RedisChatHistoryByRoomS] = []
        if lack_cnt > 0:
            if chat_histories_redis:
                next_offset: int = self.receive.data.offset + len(chat_histories_redis)
            else:
                next_offset: int = self.receive.data.offset

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
                if update_target_db:
                    await crud_history_user_mapping.bulk_update([
                        dict(id=m.id, is_read=True) for m in update_target_db
                    ])

                await self.session.commit()

                migrated_chat_histories_redis = [
                    await RedisChatHistoryByRoomS.from_model(m)
                    for m in chat_histories_db
                ]
        if migrated_chat_histories_redis:
            chat_histories_redis.extend(migrated_chat_histories_redis)

        self._result = chat_histories_redis
        return self._result

    @property
    def send_kwargs(self):
        assert self._result is not None, 'Run `handle()` first.'
        return dict(
            histories=self._result
        )
