from sqlalchemy import insert, select, update, delete
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
    return db_user


def update_user(db: Session, target_id: int, **kwargs):
    stmt = (
        update(user_models.User).
        where(user_models.User.id == target_id).
        values(**kwargs).
        execution_options(synchronize_session="fetch")
    )
    db.execute(stmt)


def create_session(db: Session, user_session: user_schemas.UserSessionCreate):
    user_session_dict = user_session.dict()
    stmt = (
        insert(user_models.UserSession).
        values(**user_session_dict)
    )
    db.execute(stmt)


def get_session_by_session_id(db: Session, session_id: str):
    stmt = (
        select(user_models.UserSession).
        filter_by(session_id=session_id).
        limit(1)
    )
    return db.scalars(stmt).first()  # == db.execute(stmt).scalars().first()


def update_session(db: Session, target_id: int, **kwargs):
    stmt = (
        update(user_models.UserSession).
        where(user_models.UserSession.id == target_id).
        values(**kwargs).
        execution_options(synchronize_session="fetch")
    )
    db.execute(stmt)


def delete_session(db: Session, target_id: int):
    stmt = (
        delete(user_models.UserSession).
        where(user_models.UserSession.id == target_id).
        execution_options(synchronize_session="fetch")
    )
    db.execute(stmt)
