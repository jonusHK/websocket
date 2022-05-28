from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server.crud import user as user_crud
from server.routers import get_db
from server.schemas import user as user_schemas

router = APIRouter(
    prefix="/users"
)


@router.post("/")
def create_user(user: user_schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = user_crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    try:
        user = user_crud.create_user(db=db, user=user)
    except Exception as e:
        return {
            'response': 0,
            'error': {
                'msg': str(e)
            }
        }

    return {
        'response': 1,
        'data': {
            'id': user.id
        }
    }
