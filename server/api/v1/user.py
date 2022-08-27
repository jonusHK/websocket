import datetime
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from server.core.authentications import SessionData, backend, cookie, verifier
from server.core.utils import verify_password
from server.crud.user import UserCRUD
from server.db.databases import get_async_session
from server.schemas import user as user_schemas

router = APIRouter()


@router.post(
    "/signup",
    response_model=user_schemas.User,
    response_model_include={"id"},
    status_code=status.HTTP_201_CREATED
)
async def signup(user_s: user_schemas.UserCreate, session: AsyncSession = Depends(get_async_session)):
    db_user = await UserCRUD(session).get_user_by_uid(uid=user_s.uid)
    if db_user:
        raise HTTPException(status_code=400, detail="Already signed up.")

    user = await UserCRUD(session).create_user(user=user_s)
    await session.commit()
    await session.refresh(user)
    return jsonable_encoder(user)


@router.post(
    "/login",
    response_model=user_schemas.User,
    response_model_include={"id"}
)
async def login(data: SessionData, response: Response, session: AsyncSession = Depends(get_async_session)):
    session_id = uuid4()
    user = await UserCRUD(session).get_user_by_uid(data.uid)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid uid.")
    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid password.")

    await backend.create(session_id, data, session)
    cookie.attach_to_response(response, session_id)
    await UserCRUD(session).update_user(user.id, last_login=datetime.datetime.now())
    await session.commit()
    await session.refresh(user)
    return jsonable_encoder(user)


@router.get("/whoami", dependencies=[Depends(cookie)])
async def whoami(session_data: SessionData = Depends(verifier)):
    return session_data


@router.post("/logout")
async def logout(
        response: Response, session_id: UUID = Depends(cookie), session: AsyncSession = Depends(get_async_session)):
    await backend.delete(session_id, session)
    cookie.delete_from_response(response)
    await session.commit()
    return
