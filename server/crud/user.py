from sqlalchemy import insert, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.utils import hash_password
from server.models.user import User, UserSession
from server.schemas.user import UserCreate, UserSessionCreate


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

    async def create_user(self, user: UserCreate):
        user_dict = user.dict()
        user_dict.update({
            'password': hash_password(user.password)
        })
        user = User(**user_dict)
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

    async def create_session(self, user_session: UserSessionCreate):
        user_session_dict = user_session.dict()
        stmt = (
            insert(UserSession).
            values(**user_session_dict)
        )
        await self.session.execute(stmt)

    async def get_session_by_session_id(self, session_id: str):
        stmt = (
            select(UserSession).
            filter_by(session_id=session_id).
            limit(1)
        )
        results = await self.session.execute(stmt)
        session = results.scalar_one_or_none()
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
