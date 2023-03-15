import base64
import uuid
from datetime import datetime
from io import BytesIO
from typing import List

from server.api.common import AsyncRedisHandler
from server.api.websocket.chat import ChatHandler
from server.core.enums import SendMessageType, ChatHistoryType
from server.core.externals.redis.schemas import RedisChatHistoryFileS, RedisChatHistoryByRoomS, \
    RedisChatHistoriesByRoomS, RedisChatRoomInfoS, RedisUserProfileByRoomS
from server.crud.service import ChatHistoryCRUD, ChatRoomUserAssociationCRUD
from server.db.databases import settings
from server.models import ChatHistory, ChatHistoryFile
from server.schemas.base import WebSocketFileS


class FileHandler(ChatHandler):

    send_type = SendMessageType.MULTICAST

    async def handle(self, **kwargs):
        crud_chat_history = ChatHistoryCRUD(self.session)
        crud_room_user_mapping = ChatRoomUserAssociationCRUD(self.session)

        redis_handler: AsyncRedisHandler = kwargs.get('redis_handler')
        user_profile_id: int = kwargs.get('user_profile_id')
        user_profiles_redis: List[RedisUserProfileByRoomS] = kwargs.get('user_profiles_redis')
        room_id: int = kwargs.get('room_id')
        room_redis: RedisChatRoomInfoS = kwargs.get('room_redis')
        now: datetime = datetime.now().astimezone()

        redis_id = uuid.uuid4().hex
        chat_history_db: ChatHistory = await crud_chat_history.create(
            redis_id=redis_id,
            room_id=room_id,
            user_profile_id=user_profile_id,
            type=ChatHistoryType.FILE
        )
        await self.session.flush()
        await self.session.refresh(chat_history_db)

        chat_files_db: List[ChatHistoryFile] = []
        _idx = 1
        converted_files = [
            WebSocketFileS(
                content=BytesIO(base64.b64decode(f.content)),
                filename=f.filename,
                content_type=f.content_type
            ) for f in self.receive.data.files
        ]
        async for o in ChatHistoryFile.files_to_models(
            self.session,
            converted_files,
            root='chat_upload/',
            uploaded_by_id=user_profile_id,
            bucket_name=settings.aws_storage_bucket_name,
        ):
            o.chat_history_id = chat_history_db.id
            o.order = _idx
            chat_files_db.append(o)
            _idx += 1

        try:
            if len(chat_files_db) == 1:
                await chat_files_db[0].upload()
            else:
                await ChatHistoryFile.asynchronous_upload(*chat_files_db)
        except Exception as exc:
            self.logger.error(f'Failed to upload files: {exc}')
            return
        finally:
            for o in chat_files_db:
                o.close()

        self.session.add_all(chat_files_db)
        await self.session.commit()
        for o in chat_files_db:
            await self.session.refresh(o)

        files_s: List[RedisChatHistoryFileS] = await RedisChatHistoryFileS.generate_files_schema(
            chat_files_db, presigned=True
        )
        chat_history_redis: RedisChatHistoryByRoomS = RedisChatHistoryByRoomS(
            id=chat_history_db.id,
            redis_id=redis_id,
            user_profile_id=user_profile_id,
            files=files_s,
            read_user_ids=list({user_profile_id} | set(room_redis.connected_profile_ids)),
            type=chat_history_db.type.name.lower(),
            timestamp=now.timestamp(),
            date=now.date().isoformat(),
            is_active=chat_history_db.is_active
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
