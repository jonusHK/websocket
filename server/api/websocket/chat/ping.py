from server.api.websocket.chat import ChatHandler
from server.core.enums import SendMessageType


class PingHandler(ChatHandler):

    send_type = SendMessageType.UNICAST

    async def handle(self, **kwargs):
        self._result = True
        return self._result

    @property
    def send_kwargs(self):
        assert self._result is not None, 'Run `handle()` first.'
        return dict(
            pong=self._result
        )
