from datetime import datetime

from pydantic import BaseModel

from server.base.schemas import S3MediaBase


class UserBase(BaseModel):
    uid: str
    name: str
    mobile: str
    email: str
    last_login: datetime
    is_staff = bool
    is_active = bool


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int

    class Config:
        orm_model = True


class UserProfileBase(BaseModel):
    nickname: str
    status_message: str
    is_default: bool
    is_active: bool


class UserProfileCreate(UserProfileBase):
    pass


class UserProfile(UserProfileBase):
    id: int
    user_id: int
    created: datetime


class UserRelationshipBase(BaseModel):
    type: int
    favorites: int
    is_hidden: int
    is_forbidden: int
    is_active: int


class UserRelationshipCreate(UserRelationshipBase):
    other_profile_id: int


class UserRelationship(UserRelationshipBase):
    id: int
    my_profile_id: int


class UserProfileImageBase(S3MediaBase):
    type: int
    is_default: int
    is_active: int


class UserProfileImageCreate(UserProfileImageBase):
    pass


class UserProfileImage(UserProfileImageBase):
    id: int
    user_profile_id: int
    created: datetime
