from datetime import datetime
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.api import ExceptionHandlerRoute
from server.core.authentications import SessionData, backend, cookie, verifier, RoleChecker
from server.core.enums import UserType
from server.core.utils import verify_password
from server.crud.user import UserCRUD, UserProfileCRUD
from server.db.databases import get_async_session
from server.models import UserSession
from server.schemas.user import UserS, UserSessionS, UserCreateS

router = APIRouter(route_class=ExceptionHandlerRoute)


@router.post(
    "/signup",
    response_model=UserS,
    response_model_include={"id", "uid"},
    status_code=status.HTTP_201_CREATED
)
async def signup(user_s: UserCreateS, session: AsyncSession = Depends(get_async_session)):
    user_crud = UserCRUD(session)
    user_profile_crud = UserProfileCRUD(session)

    db_user = await user_crud.get_user_by_uid(uid=user_s.uid)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already signed up.")
    user = await user_crud.create(**user_s.dict())

    await user_profile_crud.create(user=user, nickname=user.name, is_default=True)
    await session.commit()

    return UserS.from_orm(user)


@router.post(
    "/login",
    response_model=UserS,
    response_model_include={"id"}
)
async def login(data: SessionData, response: Response, session: AsyncSession = Depends(get_async_session)):
    session_id = uuid4()
    user = await UserCRUD(session).get_user_by_uid(data.uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid uid.")
    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password.")

    await backend.create(session_id, data, session)
    cookie.attach_to_response(response, session_id)  # 저장 되는 쿠키 값: str(cookie.signer.dumps(session_id.hex))
    await UserCRUD(session).update_user(user.id, last_login=datetime.now().astimezone())
    await session.commit()
    return UserS.from_orm(user)


@router.get("/whoami", dependencies=[Depends(cookie)])
async def whoami(user_session: UserSession = Depends(verifier)):
    return UserSessionS.from_orm(user_session)


@router.get("/permission", dependencies=[Depends(cookie), Depends(RoleChecker([UserType.USER]))])
async def permission_test():
    return {"detail": "ok"}


@router.post("/logout")
async def logout(
        response: Response, session_id: UUID = Depends(cookie), session: AsyncSession = Depends(get_async_session)):
    await backend.delete(session_id, session)
    cookie.delete_from_response(response)
    await session.commit()
    return
