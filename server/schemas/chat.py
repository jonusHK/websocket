from typing import Optional, List

from pydantic import BaseModel, validator

from server.core.enums import ChatType


class ChatRoomRequest(BaseModel):
    user_profile_id: int
    target_profile_ids: List[int]
    room_id: Optional[int] = None


class ChatDataBase(BaseModel):
    text: Optional[str] = None
    history_ids: Optional[List[int]] = None
    file_urls: Optional[List[str]] = None
    is_active: bool = True


class ChatReceiveData(ChatDataBase):
    pass


class ChatSendData(ChatDataBase):
    user_profile_id: int
    nickname: str
    timestamp: int


class ChatReceiveForm(BaseModel):
    type: str
    data: ChatReceiveData

    @validator("type")
    def check_type(cls, v):
        if v not in (e.name.lower() for e in ChatType):
            raise ValueError("Invalid `type` value.")
        return v


class ChatSendForm(BaseModel):
    type: str
    data: ChatSendData

    @validator("type")
    def check_type(cls, v):
        if v not in (e.name.lower() for e in ChatType):
            raise ValueError("Invalid `type` value.")
        return v
