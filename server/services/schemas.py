from datetime import datetime

from pydantic import BaseModel


class ChatRoomBase(BaseModel):
    name: str


class ChatRoomCreate(ChatRoomBase):
    pass


class ChatRoom(ChatRoomBase):
    id: int
    created: datetime


class ChatRoomUserMappingBase(BaseModel):
    name: str


class ChatRoomUserMappingCreate(ChatRoomUserMappingBase):
    pass


class ChatRoomUserMapping(ChatRoomUserMappingBase):
    room_id: int
    user_profile_id: int
    created: datetime


class ChatHistoryBase(BaseModel):
    contents: str
    is_active: bool


class ChatHistoryCreate(ChatHistoryBase):
    pass


class ChatHistory(ChatHistoryBase):
    id: int
    room_id: int
    s3_media_id: int
    created: datetime
