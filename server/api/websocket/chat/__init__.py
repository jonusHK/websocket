import logging
from abc import abstractmethod
from typing import Iterable, Tuple, List

from sqlalchemy.ext.asyncio import AsyncSession

from server.core.enums import SendMessageType
from server.core.externals.redis.schemas import RedisChatHistoryByRoomS
from server.models import ChatHistory
from server.schemas.chat import ChatReceiveFormS, ChatSendFormS, ChatSendDataS


class ChatHandler:

    logger = logging.getLogger('chat')
    send_type: SendMessageType = None

    _result = None

    def __init__(self, receive: ChatReceiveFormS, session: AsyncSession):
        self.receive = receive
        self.session = session

    @staticmethod
    async def get_chat_histories(models: Iterable[ChatHistory]) -> List[RedisChatHistoryByRoomS]:
        return [
            await RedisChatHistoryByRoomS.from_model(m)
            for m in models
        ]

    @abstractmethod
    async def handle(self, **kwargs) -> RedisChatHistoryByRoomS | List[RedisChatHistoryByRoomS] | None:
        raise NotImplementedError

    async def execute(self, **kwargs) -> RedisChatHistoryByRoomS | List[RedisChatHistoryByRoomS] | None:
        return await self.handle(**kwargs)

    @property
    @abstractmethod
    def send_kwargs(self):
        raise NotImplementedError

    @property
    def send_response(self) -> Tuple[ChatSendFormS, SendMessageType]:
        return ChatSendFormS(
            type=self.receive.type, data=ChatSendDataS(**self.send_kwargs)
        ), self.send_type
