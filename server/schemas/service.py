from datetime import datetime

from pydantic import BaseModel, Extra


class ChatRoomBaseS(BaseModel):
    name: str
    is_active: bool = True


class ChatRoomCreateS(ChatRoomBaseS):
    pass


class ChatRoomS(ChatRoomBaseS):
    id: int
    created: datetime

    class Config:
        orm_mode = True


class ChatRoomUserAssociationBaseS(BaseModel):
    room_id: int
    user_profile_id: int


class ChatRoomUserAssociationCreateS(ChatRoomUserAssociationBaseS):
    pass


class ChatRoomUserAssociationS(ChatRoomUserAssociationBaseS):
    created: datetime

    class Config:
        orm_mode = True


class ChatHistoryBaseS(BaseModel):
    contents: str
    is_active: bool = True


class ChatHistoryCreateS(ChatHistoryBaseS):
    pass


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
