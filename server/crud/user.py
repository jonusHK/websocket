from server.core.utils import hash_password
from server.crud import CRUDBase
from server.models.user import User, UserSession, UserProfile, UserProfileImage, UserRelationship


class UserCRUD(CRUDBase):
    model = User

    async def create(self, **kwargs):
        kwargs.update({
            'uid': kwargs['email'],
            'password': hash_password(kwargs['password'])
        })
        user = User(**kwargs)
        self.session.add(user)
        return user


class UserSessionCRUD(CRUDBase):
    model = UserSession


class UserProfileCRUD(CRUDBase):
    model = UserProfile


class UserProfileImageCRUD(CRUDBase):
    model = UserProfileImage


class UserRelationshipCRUD(CRUDBase):
    model = UserRelationship
