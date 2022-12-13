import logging
from datetime import datetime
from typing import List
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from server.api import ExceptionHandlerRoute
from server.core.authentications import SessionData, backend, cookie, verifier, RoleChecker
from server.core.enums import UserType, ProfileImageType
from server.core.utils import verify_password
from server.crud.user import UserCRUD
from server.db.databases import get_async_session, settings
from server.models import UserSession, UserProfileImage, User, UserProfile
from server.schemas.user import UserS, UserSessionS, UserCreateS, UserProfileImageS, UserProfileImageUploadS

router = APIRouter(route_class=ExceptionHandlerRoute)


@router.post(
    "/signup",
    response_model=UserS,
    response_model_include={"id", "uid"},
    status_code=status.HTTP_201_CREATED
)
async def signup(user_s: UserCreateS, session: AsyncSession = Depends(get_async_session)):
    user_crud = UserCRUD(session)

    try:
        await user_crud.get(conditions=(User.uid == user_s.uid,))
    except HTTPException:
        pass
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Already signed up.')
    user = await user_crud.create(**jsonable_encoder(user_s))
    user.profiles.append(UserProfile(user=user, nickname=user.name, is_default=True))
    await session.commit()
    await session.refresh(user)

    return UserS.from_orm(user)


@router.post(
    "/login",
    response_model=UserS,
    response_model_include={"id"}
)
async def login(data: SessionData, response: Response, session: AsyncSession = Depends(get_async_session)):
    session_id = uuid4()
    crud = UserCRUD(session)

    user = await crud.get(conditions=(User.uid == data.uid,))
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid uid.")
    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password.")

    await backend.create(session_id, data, session)
    cookie.attach_to_response(response, session_id)  # 저장 되는 쿠키 값: str(cookie.signer.dumps(session_id.hex))
    await crud.update(
        conditions=(User.id == user.id,),
        values=dict(last_login=datetime.now().astimezone()))
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


# 유저 프로필, 배경 이미지 업로드
@router.post("/profile/image/upload", dependencies=[Depends(cookie)])
async def user_profile_image_upload(
    file: UploadFile,
    upload_s: UserProfileImageUploadS = Depends(),
    user_session: UserSession = Depends(verifier),
    session=Depends(get_async_session)
):
    if upload_s.user_profile_id not in [p.id for p in user_session.user.profiles]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    objects: List[UserProfileImage] = []
    async for o in UserProfileImage.files_to_models(
        session,
        [file],
        root='user_profile/',
        user_profile_id=upload_s.user_profile_id,
        type=ProfileImageType.get_by_name(upload_s.image_type),
        is_default=upload_s.is_default,
        bucket_name=settings.aws_storage_bucket_name
    ):
        objects.append(o)

    try:
        session.add_all(objects)
        await session.commit()
        for o in objects:
            await session.refresh(o)

        if len(objects) == 1:
            await objects[0].upload()
        else:
            await UserProfileImage.asynchronous_upload(*objects)
    finally:
        for o in objects:
            o.close()

    return [UserProfileImageS.from_orm(o) for o in objects]
