import datetime
from typing import Generic
from uuid import UUID

from fastapi import Depends
from fastapi import HTTPException
from fastapi_sessions.backends.session_backend import SessionModel, SessionBackend, BackendError
from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi_sessions.frontends.session_frontend import ID
from fastapi_sessions.session_verifier import SessionVerifier
from pydantic.main import BaseModel
from sqlalchemy.orm import Session

from server.crud import user as user_crud
from server.routers import get_db
from server.schemas import user as user_schemas


class SessionData(BaseModel):
    uid: str
    expiry_at: datetime | None


class DatabaseBackend(Generic[ID, SessionModel], SessionBackend[ID, SessionModel]):
    def __init__(self, _cookie_params: CookieParameters, db: Session = Depends(get_db)) -> None:
        self.cookie_params = _cookie_params
        self.db = db

    async def create(self, session_id: ID, data: SessionModel):
        user = user_crud.get_user_by_uid(self.db, data.uid)
        session_create_s = user_schemas.UserSessionCreate(
            user_id=user.id,
            session_id=session_id,
            expiry_at=datetime.datetime.now() + datetime.timedelta(seconds=self.cookie_params.max_age))
        user_crud.create_session(self.db, session_create_s)

    async def read(self, session_id: ID):
        user_session_m = user_crud.get_session_by_session_id(self.db, session_id)
        if not user_session_m:
            return
        user_session_s = user_schemas.UserSession(**user_session_m.dict())
        return user_session_s

    async def update(self, session_id: ID, data: SessionModel) -> None:
        user_session_m = user_crud.get_session_by_session_id(self.db, session_id)
        if not user_session_m:
            raise BackendError("session does not exist, cannot update")
        user_crud.update_session(self.db, user_session_m.id, **data.dict())

    async def delete(self, session_id: ID) -> None:
        user_session_m = user_crud.get_session_by_session_id(self.db, session_id)
        if not user_session_m:
            raise BackendError("session does not exist, cannot delete")
        user_crud.delete_session(self.db, user_session_m.id)


class BasicVerifier(SessionVerifier[UUID, SessionData]):
    def __init__(
        self,
        *,
        identifier: str,
        auto_error: bool,
        backend: DatabaseBackend[UUID, SessionData],
        auth_http_exception: HTTPException,
    ):
        self._identifier = identifier
        self._auto_error = auto_error
        self._backend = backend
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

    def verify_session(self, model: user_schemas.UserSession) -> bool:
        """If the session exists, it is valid"""
        return True


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
backend = DatabaseBackend[UUID, SessionData]()

verifier = BasicVerifier(
    identifier="general_verifier",
    auto_error=True,
    backend=backend,
    auth_http_exception=HTTPException(status_code=403, detail="invalid session"),
)
