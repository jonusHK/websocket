from fastapi.encoders import jsonable_encoder

from server.api.common import AsyncRedisHandler, WebSocketHandler
from server.api.websocket.chat import ChatHandler
from server.api.websocket.chat.file import FileHandler
from server.api.websocket.chat.invite import InviteHandler
from server.api.websocket.chat.lookup import LookUpHandler
from server.api.websocket.chat.message import MessageHandler
from server.api.websocket.chat.ping import PingHandler
from server.api.websocket.chat.terminate import TerminateHandler
from server.api.websocket.chat.patch import PatchHandler
from server.core.enums import ChatType, SendMessageType
from server.core.externals.redis.schemas import RedisChatRoomPubSubS


class ChatHandlerDecorator(ChatHandler):

    _handler = None

    @property
    def handler(self):
        if self._handler:
            return self._handler

        if self.receive.type == ChatType.LOOKUP:
            handler = LookUpHandler
        elif self.receive.type == ChatType.PATCH:
            handler = PatchHandler
        elif self.receive.type == ChatType.MESSAGE:
            handler = MessageHandler
        elif self.receive.type == ChatType.FILE:
            handler = FileHandler
        elif self.receive.type == ChatType.INVITE:
            handler = InviteHandler
        elif self.receive.type == ChatType.TERMINATE:
            handler = TerminateHandler
        else:
            handler = PingHandler

        self._handler = handler(self.receive, self.session)
        return self._handler

    async def handle(self, **kwargs):
        return await self.handler.handle(**kwargs)

    async def send(self, **kwargs):
        if not await self.execute(**kwargs):
            return

        ws_handler: WebSocketHandler = kwargs.get('ws_handler')
        redis_handler: AsyncRedisHandler = kwargs.get('redis_handler')
        room_id: int = kwargs.get('room_id')

        response_s, send_type = self.handler.send_response
        if send_type == SendMessageType.UNICAST:
            await ws_handler.send_json(jsonable_encoder(response_s))
        elif send_type == SendMessageType.MULTICAST:
            redis = await redis_handler.redis
            await redis.publish(RedisChatRoomPubSubS.get_key(room_id), response_s.json())
        else:
            self.handler.logger.warning(f'Invalid send type. {send_type}')

