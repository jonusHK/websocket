from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Extra

from server.core.enums import ChatRoomType


class ChatRoomBaseS(BaseModel):
    name: Optional[str] = None
    type: ChatRoomType
    is_active: bool = True


class ChatRoomS(ChatRoomBaseS):
    id: int
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ChatRoomType: lambda v: v.name.lower()
        }


class ChatRoomUserAssociationBaseS(BaseModel):
    room_id: int
    user_profile_id: int
    room_name: str


class ChatRoomUserAssociationS(ChatRoomUserAssociationBaseS):
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatHistoryBaseS(BaseModel):
    contents: str
    is_active: bool = True


class ChatHistoryS(ChatHistoryBaseS):
    id: int
    room_id: int
    created: datetime

    class Config:
        orm_mode = True
        extra = Extra.allow
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
