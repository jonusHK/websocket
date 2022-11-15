from typing import Optional, List

from pydantic import BaseModel, validator

from server.core.enums import ChatType


class ChatRoomCreate(BaseModel):
    user_profile_id: int
    target_profile_ids: List[int]


# TODO ChatType 에 따라 분기 처리
class ChatDataBase(BaseModel):
    text: Optional[str] = None
    history_ids: Optional[List[int]] = None
    file_ids: Optional[List[int]] = None
    timestamp: float | int
    is_active: bool = True


class ChatReceiveData(ChatDataBase):
    target_user_profile_ids: Optional[List[int]] = None
    is_read: Optional[bool] = None
    offset: Optional[int] = None
    limit: Optional[int] = None
    order_by: str = 'created'


class ChatSendData(ChatDataBase):
    from server.core.externals.redis.schemas import RedisChatHistoryByRoomS, RedisUserProfileByRoomS, RedisFileS
    user_profile_id: Optional[int] = None
    nickname: Optional[str] = None
    histories: Optional[List[RedisChatHistoryByRoomS]] = None
    user_profiles: Optional[List[RedisUserProfileByRoomS]] = None
    files: Optional[List[RedisFileS]] = None


class ChatReceiveForm(BaseModel):
    type: str
    data: ChatReceiveData

    @validator("type")
    def get_type(cls, v):
        if v not in (e.name.lower() for e in ChatType):
            raise ValueError("Invalid `type` value.")
        return ChatType.get_by_name(v)


class ChatSendForm(BaseModel):
    type: ChatType
    data: ChatSendData

    @validator("type")
    def get_type(cls, v):
        if v not in ChatType:
            raise ValueError("Invalid `type` value.")
        return v.name.lower()
