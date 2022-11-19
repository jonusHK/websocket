from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Extra


class ChatRoomBase(BaseModel):
    name: str
    is_active: bool = True


class ChatRoomCreate(ChatRoomBase):
    pass


class ChatRoom(ChatRoomBase):
    id: int
    created: datetime

    class Config:
        orm_mode = True


class ChatRoomUserAssociationBase(BaseModel):
    room_id: int
    user_profile_id: int


class ChatRoomUserAssociationCreate(ChatRoomUserAssociationBase):
    pass


class ChatRoomUserAssociation(ChatRoomUserAssociationBase):
    created: datetime

    class Config:
        orm_mode = True


class ChatHistoryBase(BaseModel):
    contents: str
    is_active: bool = True


class ChatHistoryCreate(ChatHistoryBase):
    pass


class ChatHistory(ChatHistoryBase):
    id: int
    room_id: int
    created: datetime

    class Config:
        orm_mode = True
        extra = Extra.allow
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
