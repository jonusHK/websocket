import datetime
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from starlette import status

from server.core.authentications import SessionData, backend, cookie, verifier
from server.core.utils import verify_password
from server.crud import user as user_crud
from server.api import get_db
from server.schemas import user as user_schemas

router = APIRouter()


@router.post(
    "/signup",
    response_model=user_schemas.User,
    response_model_include={"id"},
    status_code=status.HTTP_201_CREATED
)
async def signup(user: user_schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = user_crud.get_user_by_email(db=db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Already signed up.")

    user = user_crud.create_user(db=db, user=user)
    db.commit()
    db.refresh(user)
    return jsonable_encoder(user)


@router.post(
    "/login",
    response_model=user_schemas.User,
    response_model_include={"id"}
)
async def login(data: SessionData, response: Response, db: Session = Depends(get_db)):
    session = uuid4()
    user = user_crud.get_user_by_uid(db, data.uid)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid uid.")
    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid password.")

    await backend.create(session, data, db)
    cookie.attach_to_response(response, session)
    user_crud.update_user(db, user.id, last_login=datetime.datetime.now())
    db.commit()
    db.refresh(user)
    return jsonable_encoder(user)


@router.get("/whoami", dependencies=[Depends(cookie)])
async def whoami(session_data: SessionData = Depends(verifier)):
    return session_data


@router.post("/logout")
async def logout(response: Response, session_id: UUID = Depends(cookie), db: Session = Depends(get_db)):
    await backend.delete(session_id, db)
    cookie.delete_from_response(response)
    db.commit()
    return
