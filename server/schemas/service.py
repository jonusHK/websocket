from datetime import datetime

from pydantic import BaseModel


class ChatRoomBase(BaseModel):
    name: str


class ChatRoomCreate(ChatRoomBase):
    pass


class ChatRoom(ChatRoomBase):
    id: int
    created: datetime

    class Config:
        orm_model = True


class ChatRoomUserAssociationBase(BaseModel):
    name: str


class ChatRoomUserAssociationCreate(ChatRoomUserAssociationBase):
    pass


class ChatRoomUserMapping(ChatRoomUserAssociationBase):
    room_id: int
    user_profile_id: int
    created: datetime

    class Config:
        orm_model = True


class ChatHistoryBase(BaseModel):
    contents: str
    is_active: bool = True


class ChatHistoryCreate(ChatHistoryBase):
    pass


class ChatHistory(ChatHistoryBase):
    id: int
    room_id: int
    s3_media_id: int
    created: datetime

    class Config:
        orm_model = True
