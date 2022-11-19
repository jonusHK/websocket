from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from server.schemas import base as base_schemas


class UserBase(BaseModel):
    uid: str
    name: str
    mobile: str
    email: str
    is_superuser: bool = False
    is_staff: bool = False
    is_active: bool = True


class UserCreate(UserBase):
    uid: Optional[str] = None
    password: str


class User(UserBase):
    id: int
    last_login: Optional[datetime] = None

    class Config:
        orm_mode = True


class UserProfileBase(BaseModel):
    user_id: int
    nickname: str
    status_message: Optional[str] = None
    is_default: int = False
    is_active: int = True


class UserProfileCreate(UserProfileBase):
    pass


class UserProfile(UserProfileBase):
    id: int
    created: datetime

    class Config:
        orm_mode = True


class UserRelationshipBase(BaseModel):
    my_profile_id: int
    other_profile_id: int
    type: int
    favorites: int = False
    is_hidden: int = False
    is_forbidden: int = False
    is_active: int = True


class UserRelationshipCreate(UserRelationshipBase):
    pass


class UserRelationship(UserRelationshipBase):
    id: int

    class Config:
        orm_mode = True


class UserProfileImageBase(base_schemas.S3MediaBase):
    type: int
    user_profile_id: int
    is_default: int = False
    is_active: int = True


class UserProfileImageCreate(UserProfileImageBase):
    pass


class UserProfileImage(UserProfileImageBase):
    id: int
    created: datetime

    class Config:
        orm_mode = True


class UserSessionBase(BaseModel):
    user_id: int
    session_id: str
    expiry_at: datetime


class UserSessionCreate(UserSessionBase):
    pass


class UserSession(UserSessionBase):
    id: int

    class Config:
        orm_mode = True
