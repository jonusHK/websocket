from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from starlette import status

from server.crud import user as user_crud
from server.routers import get_db
from server.schemas import user as user_schemas
from server.schemas.user import User as UserSchema

router = APIRouter(
    prefix="/users"
)


@router.post(
    "/",
    response_model=UserSchema,
    response_model_include={"id"},
    status_code=status.HTTP_201_CREATED
)
def create_user(user: user_schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = user_crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = user_crud.create_user(db=db, user=user)
    return jsonable_encoder(user)
