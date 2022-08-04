from sqlalchemy.orm import Session

from server.core.utils import hash_password
from server.models import user as user_models
from server.schemas import user as user_schemas


def get_user_by_uid(db: Session, uid: str):
    return db.query(user_models.User).filter(user_models.User.uid == uid).first()


def get_user_by_email(db: Session, email: str):
    return db.query(user_models.User).filter(user_models.User.email == email).first()


def create_user(db: Session, user: user_schemas.UserCreate):
    user_dict = user.dict()
    user_dict.update({
        'password': hash_password(user.password)
    })
    db_user = user_models.User(**user_dict)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user
