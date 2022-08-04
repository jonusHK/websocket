from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from starlette import status

from server.core.utils import verify_password
from server.crud import user as user_crud
from server.routers import get_db
from server.schemas import user as user_schemas
from server.models import user as user_models

router = APIRouter(
    prefix="/users"
)

# ex. https://{{domain}}{{root_path}}/token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_user(token: str = Depends(oauth2_scheme)):
    user = user_models.User()  # TODO 해당 토큰을 갖고 있으며, is_active = True 인 user 추출
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


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


@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = user_crud.get_user_by_uid(db, uid=form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username.")

    if not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect password.")

    return {"access_token": user.uid, "token_type": "bearer"}
