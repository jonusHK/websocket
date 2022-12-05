from typing import Optional, List

from pydantic import BaseModel, validator

from server.core.enums import ChatType


class ChatRoomCreateParamS(BaseModel):
    user_profile_id: int
    target_profile_ids: List[int]


# TODO ChatType 에 따라 분기 처리
class ChatDataBaseS(BaseModel):
    text: Optional[str] = None
    history_ids: Optional[List[int]] = None
    timestamp: float | int
    is_active: bool = True


class ChatReceiveFileS(BaseModel):
    content: str
    content_type: str
    filename: str


class ChatReceiveDataS(ChatDataBaseS):
    target_user_profile_ids: Optional[List[int]] = None
    files: list[ChatReceiveFileS] = None
    is_read: Optional[bool] = None
    offset: Optional[int] = None
    limit: Optional[int] = None
    order_by: str = 'created'


class ChatSendDataS(ChatDataBaseS):
    from server.core.externals.redis.schemas import RedisChatHistoryByRoomS, RedisUserProfileByRoomS, RedisUserImageFileS, RedisChatHistoryFileS
    user_profile_id: Optional[int] = None
    nickname: Optional[str] = None
    histories: Optional[List[RedisChatHistoryByRoomS]] = None
    user_profiles: Optional[List[RedisUserProfileByRoomS]] = None
    files: Optional[List[RedisChatHistoryFileS | RedisUserImageFileS]] = None


class ChatReceiveFormS(BaseModel):
    type: str
    data: ChatReceiveDataS

    @validator("type")
    def get_type(cls, v):
        if v not in (e.name.lower() for e in ChatType):
            raise ValueError("Invalid `type` value.")
        return ChatType.get_by_name(v)


class ChatSendFormS(BaseModel):
    type: ChatType
    data: ChatSendDataS

    @validator("type")
    def get_type(cls, v):
        if v not in ChatType:
            raise ValueError("Invalid `type` value.")
        return v.name.lower()
