from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from server.schemas.base import S3MediaBaseS


class UserBase(BaseModel):
    uid: str
    name: str
    mobile: str
    email: str
    is_superuser: bool = False
    is_staff: bool = False
    is_active: bool = True


class UserCreateS(UserBase):
    uid: Optional[str] = None
    password: str


class UserS(UserBase):
    id: int
    last_login: Optional[datetime] = None

    class Config:
        orm_mode = True


class UserProfileBaseS(BaseModel):
    user_id: int
    nickname: str
    status_message: Optional[str] = None
    is_default: int = False
    is_active: int = True


class UserProfileCreateS(UserProfileBaseS):
    pass


class UserProfileS(UserProfileBaseS):
    id: int
    created: datetime

    class Config:
        orm_mode = True


class UserRelationshipBaseS(BaseModel):
    my_profile_id: int
    other_profile_id: int
    type: int
    favorites: int = False
    is_hidden: int = False
    is_forbidden: int = False
    is_active: int = True


class UserRelationshipCreateS(UserRelationshipBaseS):
    pass


class UserRelationshipS(UserRelationshipBaseS):
    id: int

    class Config:
        orm_mode = True


class UserProfileImageBaseS(S3MediaBaseS):
    type: int
    user_profile_id: int
    is_default: int = False
    is_active: int = True


class UserProfileImageCreateS(UserProfileImageBaseS):
    pass


class UserProfileImageS(UserProfileImageBaseS):
    id: int
    created: datetime

    class Config:
        orm_mode = True


class UserSessionBaseS(BaseModel):
    user_id: int
    session_id: str
    expiry_at: datetime


class UserSessionCreateS(UserSessionBaseS):
    pass


class UserSessionS(UserSessionBaseS):
    id: int

    class Config:
        orm_mode = True
