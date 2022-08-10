from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from starlette import status

from server.core.authentications import SessionData, backend, cookie, verifier
from server.crud import user as user_crud
from server.routers import get_db
from server.schemas import user as user_schemas

router = APIRouter(
    prefix="/users"
)


@router.post(
    "/",
    response_model=user_schemas.User,
    response_model_include={"id"},
    status_code=status.HTTP_201_CREATED
)
async def create_user(user: user_schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = user_crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = user_crud.create_user(db=db, user=user)
    return jsonable_encoder(user)


@router.post("/create_session/{uid}")
async def create_session(uid: str, response: Response):
    session = uuid4()
    data = SessionData(uid=uid)

    await backend.create(session, data)
    cookie.attach_to_response(response, session)
    return f'created session for {uid}'


@router.get("/whoami", dependencies=[Depends(cookie)])
async def whoami(session_data: SessionData = Depends(verifier)):
    return session_data


@router.post("/delete_session")
async def del_session(response: Response, session_id: UUID = Depends(cookie)):
    await backend.delete(session_id)
    cookie.delete_from_response(response)
    return "deleted session"
