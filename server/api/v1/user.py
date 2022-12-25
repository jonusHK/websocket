import logging
from datetime import datetime
from typing import List, Dict, Any
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from server.api import ExceptionHandlerRoute
from server.api.common import AuthValidator
from server.core.authentications import SessionData, backend, cookie, verifier, RoleChecker
from server.core.enums import UserType, ProfileImageType, RelationshipType, ResponseCode
from server.core.exceptions import ClassifiableException
from server.core.utils import verify_password
from server.crud.user import UserCRUD, UserProfileCRUD
from server.db.databases import get_async_session, settings
from server.models import UserSession, UserProfileImage, User, UserProfile, UserRelationship
from server.schemas.user import UserS, UserSessionS, UserCreateS, UserProfileImageS, UserProfileImageUploadS, \
    UserProfileS, UserRelationshipS, LoginUserS

router = APIRouter(route_class=ExceptionHandlerRoute)


@router.post(
    "/signup",
    response_model=UserS,
    response_model_include={"id", "uid"},
    status_code=status.HTTP_201_CREATED
)
async def signup(user_s: UserCreateS, session: AsyncSession = Depends(get_async_session)):
    error_code = None
    if not user_s.email:
        error_code = ResponseCode.INVALID_UID
    elif not user_s.password:
        error_code = ResponseCode.INVALID_PASSWORD
    elif not user_s.name:
        error_code = ResponseCode.INVALID_USER_NAME
    elif not user_s.mobile:
        error_code = ResponseCode.INVALID_MOBILE

    if error_code:
        raise ClassifiableException(code=error_code)

    user_crud = UserCRUD(session)
    try:
        await user_crud.get(conditions=(User.uid == user_s.email,))
    except HTTPException:
        pass
    else:
        raise ClassifiableException(code=ResponseCode.ALREADY_SIGNED_UP)
    user = await user_crud.create(**jsonable_encoder(user_s))
    user.profiles.append(UserProfile(user=user, nickname=user.name, is_default=True))
    await session.commit()
    await session.refresh(user)

    return UserS.from_orm(user)


@router.post("/login", response_model=LoginUserS)
async def login(data: SessionData, response: Response, session: AsyncSession = Depends(get_async_session)):
    session_id = uuid4()
    crud = UserCRUD(session)

    try:
        user = await crud.get(
            conditions=(User.uid == data.uid,),
            options=[
                selectinload(User.profiles)
                .selectinload(UserProfile.images)
            ])
    except HTTPException:
        raise ClassifiableException(code=ResponseCode.INVALID_UID)
    if not verify_password(data.password, user.password):
        raise ClassifiableException(code=ResponseCode.INVALID_PASSWORD)

    await backend.create(session_id, data, session)
    cookie.attach_to_response(response, session_id)  # 저장 되는 쿠키 값: str(cookie.signer.dumps(session_id.hex))
    await crud.update(
        conditions=(User.id == user.id,),
        values=dict(last_login=datetime.now().astimezone()))
    await session.commit()

    user_profile = next((p for p in user.profiles if p.is_default), None)
    return LoginUserS(
        user=UserS.from_orm(user),
        profile=UserProfileS.from_orm(user_profile) if user_profile else None)


@router.get("/whoami", dependencies=[Depends(cookie)])
async def whoami(user_session: UserSession = Depends(verifier)):
    return UserSessionS.from_orm(user_session)


@router.post("/logout")
async def logout(
        response: Response, session_id: UUID = Depends(cookie), session: AsyncSession = Depends(get_async_session)):
    await backend.delete(session_id, session)
    cookie.delete_from_response(response)
    await session.commit()
    return


# 유저 프로필 상세 정보
@router.get('/profile/{user_profile_id}')
async def user_profile_detail(user_profile_id: int, session=Depends(get_async_session)):
    crud = UserProfileCRUD(session)
    user_profile: UserProfile = await crud.get(
        conditions=(UserProfile.id == user_profile_id,),
        options=[selectinload(UserProfile.images)])

    user_profile_dict = jsonable_encoder(UserProfileS.from_orm(user_profile))
    if user_profile.images:
        presigned_images: List[Dict[str, Any]] = [
            r.result() for r in await UserProfileImage.asynchronous_presigned_url(*user_profile.images)
        ]
        for image in user_profile_dict['images']:
            image.update({
                'url': next((im['url'] for im in presigned_images if im['id'] == image['id']), None)
            })
    return user_profile_dict


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


@router.post(
    '/relationship/{user_profile_id}/create',
    dependencies=[Depends(cookie)],
    status_code=status.HTTP_201_CREATED)
async def create_relationship(
    user_profile_id: int,
    other_profile_id: int,
    relation_type: str = RelationshipType.FRIEND.name.lower(),
    user_session: UserSession = Depends(verifier),
    session=Depends(get_async_session)
):
    crud_user_profile = UserProfileCRUD(session)

    # 권한 검증
    AuthValidator.validate_user_profile(user_session, user_profile_id)

    other_profile: UserProfile = await crud_user_profile.get(
        conditions=(
            UserProfile.id == other_profile_id,
            UserProfile.is_active == 1))
    user_profile: UserProfile = await crud_user_profile.get(
        conditions=(
            UserProfile.id == user_profile_id,
            UserProfile.is_active == 1),
        options=[
            selectinload(UserProfile.followings)
        ]
    )
    relation_type: RelationshipType = RelationshipType.get_by_name(relation_type)
    if next((f for f in user_profile.followings if
             f.other_profile_id == other_profile_id and f.type == relation_type), None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Already following relationship.')

    relationship = UserRelationship(
        my_profile_id=user_profile_id,
        other_profile_id=other_profile_id,
        other_profile_nickname=other_profile.nickname,
        type=relation_type
    )
    user_profile.followings.append(relationship)
    await session.commit()
    await session.refresh(relationship)

    return UserRelationshipS.from_orm(relationship)


@router.get('/relationship/{user_profile_id}/search', dependencies=[Depends(cookie)])
async def search_relationship(
    user_profile_id: int,
    nickname: str,
    user_session: UserSession = Depends(verifier),
    session=Depends(get_async_session)
):
    crud_user_profile = UserProfileCRUD(session)

    # 권한 검증
    AuthValidator.validate_user_profile(user_session, user_profile_id)

    user_profile: UserProfile = await crud_user_profile.get(
        conditions=(
            UserProfile.id == user_profile_id,
            UserProfile.is_active == 1),
        options=[
            selectinload(UserProfile.followings).
            joinedload(UserRelationship.other_profile).
            selectinload(UserProfile.images)
        ]
    )
    searched_profiles: List[UserProfile] = [
        f.other_profile for f in user_profile.followings
        if nickname in f.other_profile_nickname and
        f.is_active and not f.is_hidden and not f.is_forbidden
    ]

    return [UserProfileS.from_orm(p) for p in searched_profiles]
