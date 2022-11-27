from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from server.core.utils import hash_password
from server.crud import CRUDBase
from server.models.user import User, UserSession, UserProfile, UserProfileImage
from server.schemas.user import UserSessionCreateS


# TODO CRUDBase 상속
class UserCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_uid(self, uid: str):
        stmt = select(User).filter_by(uid=uid)
        results = await self.session.execute(stmt)
        user = results.scalar_one_or_none()
        return user

    async def get_user_by_email(self, email: str):
        stmt = select(User).filter_by(email=email)
        results = await self.session.execute(stmt)
        user = results.scalar_one_or_none()
        return user

    async def create(self, **kwargs):
        kwargs.update({
            "uid": kwargs["email"],
            "password": hash_password(kwargs["password"])
        })
        user = User(**kwargs)
        self.session.add(user)
        return user

    async def update_user(self, target_id: int, **kwargs):
        stmt = (
            update(User).
            where(User.id == target_id).
            values(**kwargs).
            execution_options(synchronize_session="fetch")
        )
        await self.session.execute(stmt)

    async def get_session_by_session_id(self, session_id: str):
        stmt = (
            select(UserSession).
            filter_by(session_id=session_id).
            options(
                contains_eager(UserSession.user)
            ).
            limit(1)
        )
        results = await self.session.execute(stmt)
        session = results.scalar_one_or_none()
        return session


# TODO CRUDBase 상속
class UserSessionCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, create_s: UserSessionCreateS):
        user_session = UserSession(**create_s.dict())
        self.session.add(user_session)
        return user_session

    async def get_session_by_session_id(self, session_id: str):
        stmt = (
            select(UserSession).
            filter_by(session_id=session_id).
            options(
                contains_eager(UserSession.user)
            ).
            limit(1)
        )
        results = await self.session.execute(stmt)
        session = results.scalar_one_or_none()
        await self.session.refresh(session)
        return session

    async def update_session(self, target_id: int, **kwargs):
        stmt = (
            update(UserSession).
            where(UserSession.id == target_id).
            values(**kwargs).
            execution_options(synchronize_session="fetch")
        )
        await self.session.execute(stmt)

    async def delete_session(self, target_id: int):
        stmt = (
            delete(UserSession).
            where(UserSession.id == target_id).
            execution_options(synchronize_session="fetch")
        )
        await self.session.execute(stmt)


class UserProfileCRUD(CRUDBase):
    model = UserProfile


class UserProfileImageCRUD(CRUDBase):
    model = UserProfileImage
