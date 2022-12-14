from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Generic, Optional, List
from uuid import UUID

from fastapi import HTTPException, Request, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi_sessions.backends.session_backend import SessionModel, BackendError
from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi_sessions.frontends.session_frontend import ID, FrontendError
from pydantic.main import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from server.core.authentications.constants import SESSION_AGE, COOKIE_NAME, SESSION_IDENTIFIER
from server.core.enums import UserType
from server.crud.user import UserCRUD, UserSessionCRUD
from server.db.databases import get_async_session, settings, async_session
from server.models import UserSession, User
from server.schemas.user import UserSessionCreateS, UserSessionS


class SessionData(BaseModel):
    uid: str
    password: str


class SessionDatabaseBackend(ABC, Generic[ID, SessionModel]):
    """Abstract class that defines methods for interacting with session data."""

    @abstractmethod
    async def create(self, session_id: ID, data: SessionModel, db: AsyncSession) -> None:
        """Create a new session."""
        raise NotImplementedError()

    @abstractmethod
    async def read(self, session_id: ID, db: AsyncSession) -> Optional[SessionModel]:
        """Read session data from the storage."""
        raise NotImplementedError()

    @abstractmethod
    async def update(self, session_id: ID, data: SessionModel, db: AsyncSession) -> None:
        """Update session data to the storage"""
        raise NotImplementedError()

    @abstractmethod
    async def delete(self, session_id: ID, db: AsyncSession) -> None:
        """Remove session data from the storage."""
        raise NotImplementedError()


class SessionDatabaseVerifier(Generic[ID, SessionModel]):
    @property
    @abstractmethod
    def identifier(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def backend(self) -> SessionDatabaseBackend[ID, SessionModel]:
        raise NotImplementedError()

    @property
    @abstractmethod
    def auto_error(self) -> bool:
        raise NotImplementedError()

    @property
    @abstractmethod
    def auth_http_exception(self) -> HTTPException:
        raise NotImplementedError()

    @abstractmethod
    def verify_session(self, model: SessionModel) -> bool:
        raise NotImplementedError()

    async def __call__(self, request: Request, session: AsyncSession = Depends(get_async_session)):
        try:
            session_id: ID | FrontendError = request.state.session_ids[self.identifier]
        except Exception:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal failure of session verification")
            else:
                return BackendError(
                    "Failed to extract the {} session from state", self.identifier)

        if isinstance(session_id, FrontendError):
            if self.auto_error:
                raise self.auth_http_exception
            return

        user_session: UserSession = await self.backend.read(session_id, session)
        session_data = UserSessionS.from_orm(user_session)
        if not self.verify_session(session_data):
            if self.auto_error:
                raise self.auth_http_exception
            return

        if not user_session.user.is_active:
            raise self.auth_http_exception

        return user_session


class DatabaseBackend(Generic[ID, SessionModel], SessionDatabaseBackend[ID, SessionModel]):
    def __init__(self, _cookie_params: CookieParameters) -> None:
        self.cookie_params = _cookie_params

    async def create(self, session_id: ID, data: SessionModel, session: AsyncSession):
        user: User = await UserCRUD(session).get(conditions=(User.uid == data.uid,))
        expiry_at = datetime.now().astimezone() + timedelta(seconds=self.cookie_params.max_age)
        session_create_s = UserSessionCreateS(
            user_id=user.id,
            session_id=str(session_id),
            expiry_at=expiry_at)
        await UserSessionCRUD(session).create(**jsonable_encoder(session_create_s))

    async def read(self, session_id: ID, session: AsyncSession):
        crud = UserSessionCRUD(session)
        try:
            user_session: UserSession = await crud.get(
                conditions=(UserSession.session_id == session_id,),
                options=[joinedload(UserSession.user).selectinload(User.profiles)])
        except HTTPException:
            raise BackendError("Session does not exist.")
        return user_session

    async def update(self, session_id: ID, data: SessionModel, session: AsyncSession) -> None:
        crud = UserSessionCRUD(session)
        try:
            user_session: UserSession = await crud.get(
                conditions=(UserSession.session_id == session_id,))
        except HTTPException:
            raise BackendError("Session does not exist, cannot update")
        await crud.update(conditions=(UserSession == user_session.id,), values=data.dict())

    async def delete(self, session_id: ID, session: AsyncSession) -> None:
        crud = UserSessionCRUD(session)
        try:
            user_session: UserSession = await crud.get(
                conditions=(UserSession.session_id == session_id,))
        except HTTPException:
            raise BackendError("Session does not exist, cannot delete")
        await crud.delete(conditions=(UserSession.id == user_session.id,))


class BasicVerifier(SessionDatabaseVerifier[UUID, SessionData]):
    def __init__(
        self,
        *,
        identifier: str,
        auto_error: bool,
        _backend: DatabaseBackend[UUID, SessionData],
        auth_http_exception: HTTPException,
    ):
        self._identifier = identifier
        self._auto_error = auto_error
        self._backend = _backend
        self._auth_http_exception = auth_http_exception

    @property
    def identifier(self):
        return self._identifier

    @property
    def backend(self):
        return self._backend

    @property
    def auto_error(self):
        return self._auto_error

    @property
    def auth_http_exception(self):
        return self._auth_http_exception

    def verify_session(self, schema: UserSessionS) -> bool:
        return schema.expiry_at.astimezone() >= datetime.now().astimezone()


cookie_params = CookieParameters(max_age=SESSION_AGE)

cookie = SessionCookie(
    cookie_name=COOKIE_NAME,
    identifier=SESSION_IDENTIFIER,
    auto_error=True,
    secret_key=settings.session_secret_key,
    cookie_params=cookie_params)

backend = DatabaseBackend[UUID, SessionData](cookie_params)

verifier = BasicVerifier(
    identifier=SESSION_IDENTIFIER,
    auto_error=True,
    _backend=backend,
    auth_http_exception=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid session."))


class RoleChecker:
    def __init__(self, allowed_roles: List[UserType]):
        self.allowed_roles = allowed_roles

    async def __call__(self, request: Request):
        async with async_session() as session:
            user_session = await verifier(request, session)
            user = user_session.user
            error_msg = None
            if not user.is_active:
                error_msg = "User is inactive."
            elif not user.is_superuser:
                has_role = False
                for role in self.allowed_roles:
                    assert isinstance(role, UserType), "Role is invalid."
                    if (
                        (role == UserType.ADMIN and user.is_staff) or
                        (role == UserType.USER and not user.is_staff)
                    ):
                        has_role = True
                if not has_role:
                    error_msg = "Unauthorized User."

            if error_msg:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

            return user
