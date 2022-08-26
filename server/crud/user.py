from sqlalchemy import insert, select, update, delete
from sqlalchemy.orm import Session

from server.core.utils import hash_password
from server.models.user import User, UserSession
from server.schemas.user import UserCreate, UserSessionCreate


def get_user_by_uid(db: Session, uid: str):
    return db.query(User).filter(User.uid == uid).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, user: UserCreate):
    user_dict = user.dict()
    user_dict.update({
        'password': hash_password(user.password)
    })
    db_user = User(**user_dict)
    db.add(db_user)
    return db_user


def update_user(db: Session, target_id: int, **kwargs):
    stmt = (
        update(User).
        where(User.id == target_id).
        values(**kwargs).
        execution_options(synchronize_session="fetch")
    )
    db.execute(stmt)


def create_session(db: Session, user_session: UserSessionCreate):
    user_session_dict = user_session.dict()
    stmt = (
        insert(UserSession).
        values(**user_session_dict)
    )
    db.execute(stmt)


def get_session_by_session_id(db: Session, session_id: str):
    stmt = (
        select(UserSession).
        filter_by(session_id=session_id).
        limit(1)
    )
    return db.scalars(stmt).first()  # == db.execute(stmt).scalars().first()


def update_session(db: Session, target_id: int, **kwargs):
    stmt = (
        update(UserSession).
        where(UserSession.id == target_id).
        values(**kwargs).
        execution_options(synchronize_session="fetch")
    )
    db.execute(stmt)


def delete_session(db: Session, target_id: int):
    stmt = (
        delete(UserSession).
        where(UserSession.id == target_id).
        execution_options(synchronize_session="fetch")
    )
    db.execute(stmt)
