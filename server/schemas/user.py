from datetime import datetime

from pydantic import BaseModel

from server.schemas import base as base_schemas


class UserBase(BaseModel):
    uid: str
    name: str
    mobile: str
    email: str
    is_staff: bool = False
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    last_login: datetime

    class Config:
        orm_model = True


class UserProfileBase(BaseModel):
    nickname: str
    status_message: str
    is_default: bool = False
    is_active: bool = True


class UserProfileCreate(UserProfileBase):
    pass


class UserProfile(UserProfileBase):
    id: int
    user_id: int
    created: datetime

    class Config:
        orm_model = True


class UserRelationshipBase(BaseModel):
    type: int
    favorites: int = False
    is_hidden: int = False
    is_forbidden: int = False
    is_active: int = True


class UserRelationshipCreate(UserRelationshipBase):
    other_profile_id: int


class UserRelationship(UserRelationshipBase):
    id: int
    my_profile_id: int

    class Config:
        orm_model = True


class UserProfileImageBase(base_schemas.S3MediaBase):
    type: int
    is_default: int = False
    is_active: int = True


class UserProfileImageCreate(UserProfileImageBase):
    pass


class UserProfileImage(UserProfileImageBase):
    id: int
    user_profile_id: int
    created: datetime

    class Config:
        orm_model = True
