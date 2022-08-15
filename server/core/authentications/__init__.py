import datetime
from abc import ABC, abstractmethod
from typing import Generic, Optional
from uuid import UUID

from fastapi import HTTPException, Request, Depends
from fastapi.encoders import jsonable_encoder
from fastapi_sessions.backends.session_backend import SessionModel, BackendError
from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi_sessions.frontends.session_frontend import ID, FrontendError
from pydantic.main import BaseModel
from sqlalchemy.orm import Session

from server.crud import user as user_crud
from server.models import user as user_models
from server.routers import get_db
from server.schemas import user as user_schemas


class SessionData(BaseModel):
    uid: str
    password: str


class SessionDatabaseBackend(ABC, Generic[ID, SessionModel]):
    """Abstract class that defines methods for interacting with session data."""

    @abstractmethod
    async def create(self, session_id: ID, data: SessionModel, db: Session) -> None:
        """Create a new session."""
        raise NotImplementedError()

    @abstractmethod
    async def read(self, session_id: ID, db: Session) -> Optional[SessionModel]:
        """Read session data from the storage."""
        raise NotImplementedError()

    @abstractmethod
    async def update(self, session_id: ID, data: SessionModel, db: Session) -> None:
        """Update session data to the storage"""
        raise NotImplementedError()

    @abstractmethod
    async def delete(self, session_id: ID, db: Session) -> None:
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

    async def __call__(self, request: Request, db: Session = Depends(get_db)):
        try:
            session_id: ID | FrontendError = request.state.session_ids[
                self.identifier
            ]
        except Exception:
            if self.auto_error:
                raise HTTPException(
                    status_code=500, detail="internal failure of session verification"
                )
            else:
                return BackendError(
                    "failed to extract the {} session from state", self.identifier
                )

        if isinstance(session_id, FrontendError):
            if self.auto_error:
                raise self.auth_http_exception
            return

        session_data = await self.backend.read(session_id, db)
        if not session_data or not self.verify_session(session_data):
            if self.auto_error:
                raise self.auth_http_exception
            return

        return session_data


class DatabaseBackend(Generic[ID, SessionModel], SessionDatabaseBackend[ID, SessionModel]):
    def __init__(self, _cookie_params: CookieParameters) -> None:
        self.cookie_params = _cookie_params

    async def create(self, session_id: ID, data: SessionModel, db: Session):
        user: user_models.User = user_crud.get_user_by_uid(db, data.uid)
        expiry_at = datetime.datetime.now() + datetime.timedelta(seconds=self.cookie_params.max_age)
        session_create_s = user_schemas.UserSessionCreate(
            user_id=user.id,
            session_id=str(session_id),  # 저장 되는 쿠키 값: str(cookie.signer.dumps(session_id.hex))
            expiry_at=expiry_at)
        user_crud.create_session(db, session_create_s)

    async def read(self, session_id: ID, db: Session):
        user_session: user_models.UserSession = user_crud.get_session_by_session_id(db, session_id)
        if not user_session:
            return

        user_session_s = user_schemas.UserSession(**jsonable_encoder(user_session))
        return user_session_s

    async def update(self, session_id: ID, data: SessionModel, db: Session) -> None:
        user_session: user_models.UserSession = user_crud.get_session_by_session_id(db, session_id)
        if not user_session:
            raise BackendError("Session does not exist, cannot update")
        user_crud.update_session(db, user_session.id, **data.dict())

    async def delete(self, session_id: ID, db: Session) -> None:
        user_session: user_models.UserSession = user_crud.get_session_by_session_id(db, str(session_id))
        if not user_session:
            raise BackendError("Session does not exist, cannot delete")
        user_crud.delete_session(db, user_session.id)


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

    def verify_session(self, schema: user_schemas.UserSession) -> bool:
        return schema.expiry_at >= datetime.datetime.now()


cookie_params = CookieParameters(max_age=7 * 24 * 60 * 60)

# Uses UUID
cookie = SessionCookie(
    cookie_name="sessionId",
    identifier="general_verifier",
    auto_error=True,
    secret_key="DONOTUSE",
    cookie_params=cookie_params,
)

# backend = InMemoryBackend[UUID, SessionData]()
backend = DatabaseBackend[UUID, SessionData](cookie_params)

verifier = BasicVerifier(
    identifier="general_verifier",
    auto_error=True,
    _backend=backend,
    auth_http_exception=HTTPException(status_code=403, detail="Invalid session"),
)
