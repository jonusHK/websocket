from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status, UploadFile, Body, Form
from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from server.api import ExceptionHandlerRoute
from server.api.common import AuthValidator, RedisHandler
from server.core.authentications import SessionData, backend, cookie, verifier
from server.core.enums import ProfileImageType, RelationshipType, ResponseCode, IntValueEnum, FollowType
from server.core.exceptions import ClassifiableException
from server.core.externals.redis.schemas import RedisFollowingsByUserProfileS, RedisFollowingByUserProfileS
from server.core.utils import verify_password, generate_random_string
from server.crud.user import UserCRUD, UserProfileCRUD, UserRelationshipCRUD
from server.db.databases import get_async_session, settings
from server.models import UserSession, UserProfileImage, User, UserProfile, UserRelationship
from server.schemas.user import (
    UserS, UserSessionS, UserCreateS, UserProfileImageS, UserProfileS, UserRelationshipS,
    LoginUserS, UserRelationshipUpdateS, UserProfileSearchS, UserProfileSearchImageS, UserProfileSearchResponseS,
    UserRelationshipSearchS, UserRelationshipSearchResponseS
)

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

    crud_user = UserCRUD(session)
    crud_user_profile = UserProfileCRUD(session)
    crud_relationship = UserRelationshipCRUD(session)
    try:
        await crud_user.get(conditions=(User.email == user_s.email,))
    except HTTPException:
        pass
    else:
        raise ClassifiableException(code=ResponseCode.DUPLICATED_EMAIL)

    try:
        await crud_user.get(conditions=(User.mobile == user_s.mobile,))
    except HTTPException:
        pass
    else:
        raise ClassifiableException(code=ResponseCode.DUPLICATED_MOBILE)

    while True:
        identity_id = generate_random_string()
        if not await crud_user_profile.list(conditions=(UserProfile.identity_id == identity_id,)):
            break

    user = await crud_user.create(**jsonable_encoder(user_s))
    user.profiles.append(
        UserProfile(
            user=user,
            identity_id=identity_id,
            nickname=user.name,
            is_default=True
        )
    )
    await session.flush()

    user_profile_id: int = user.profiles[0].id
    relationship: UserRelationship = await crud_relationship.create(
        my_profile_id=user_profile_id,
        other_profile_id=user_profile_id,
        other_profile_nickname=user.profiles[0].nickname,
        type=RelationshipType.SELF
    )
    await session.commit()
    await session.refresh(user)

    user_profile: UserProfile = await crud_user_profile.get(
        conditions=(
            UserProfile.id == user_profile_id,
            UserProfile.is_active == 1
        ),
        options=[
            selectinload(UserProfile.images),
            selectinload(UserProfile.followers)
        ])
    profile_images: List[UserProfileImage] = user_profile.images

    # Redis 데이터 추가
    redis_handler = RedisHandler()
    RedisFollowingsByUserProfileS.sadd(
        redis_handler.redis_cluster,
        user_profile_id,
        RedisFollowingsByUserProfileS.schema(
            id=user_profile_id,
            identity_id=user_profile.identity_id,
            nickname=user_profile.nickname,
            type=relationship.type.name.lower(),
            favorites=relationship.favorites,
            is_hidden=relationship.is_hidden,
            is_forbidden=relationship.is_forbidden,
            files=await redis_handler.generate_files_schema(
                UserProfileImage, [i for i in profile_images if i.is_default]
            )
        )
    )

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
        last_login=datetime.now().astimezone()
    )
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
@router.get('/profile/{user_profile_id}/{other_profile_id}', dependencies=[Depends(cookie)])
async def other_profile_detail(
    user_profile_id: int,
    other_profile_id: int,
    user_session: UserSession = Depends(verifier),
    session=Depends(get_async_session)
):
    # 권한 검증
    AuthValidator.get_user_profile(user_session, user_profile_id)

    crud = UserProfileCRUD(session)
    other_profile: UserProfile = await crud.get(
        conditions=(UserProfile.id == other_profile_id,),
        options=[
            selectinload(UserProfile.images),
            selectinload(UserProfile.followers)
        ])

    other_profile_dict = jsonable_encoder(UserProfileS.from_orm(other_profile))
    other_profile_dict.update({
        'nickname': other_profile.get_nickname_by_other(user_profile_id)
    })
    if other_profile.images:
        image_urls: List[Dict[str, Any]] = UserProfileImage.get_file_urls(*other_profile.images)
        for image in other_profile_dict['images']:
            image.update({
                'url': next((im['url'] for im in image_urls if im['id'] == image['id']), None)
            })
    relationship = next((m for m in other_profile.followers if m.my_profile_id == user_profile_id), None)
    other_profile_dict.update({
        'relationship': relationship.type.value if relationship else None
    })

    return other_profile_dict


# 유저 프로필, 배경 이미지 업로드
@router.post('/profile/image/upload', dependencies=[Depends(cookie)])
async def user_profile_image_upload(
    file: UploadFile,
    user_profile_id: int = Form(),
    image_type: str = Form(),
    is_default: bool = Form(),
    user_session: UserSession = Depends(verifier),
    session=Depends(get_async_session)
):
    # 권한 검증
    AuthValidator.get_user_profile(user_session, user_profile_id)

    objects: List[UserProfileImage] = []
    async for o in UserProfileImage.files_to_models(
        session,
        [file],
        root='user_profile/',
        uploaded_by_id=user_profile_id,
        type=ProfileImageType.get_by_name(image_type),
        is_default=is_default,
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

    # TODO 파일 URL -> CDN 변경하고나서 Redis 업데이트

    return [UserProfileImageS.from_orm(o) for o in objects]


@router.get('/profiles', dependencies=[Depends(cookie)],)
async def search_user_profiles(
    user_profile_id: Optional[int] = None,
    identity_id: Optional[str] = None,
    nickname: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
):
    crud_profile = UserProfileCRUD(session)

    request_s = UserProfileSearchS(
        id=user_profile_id,
        identity_id=identity_id,
        nickname=nickname,
    )

    if not request_s.values_except_null():
        raise HTTPException(detail='Not exists any params.', status_code=status.HTTP_404_NOT_FOUND)

    conditions = [UserProfile.is_active == 1]
    for k, v in request_s.values_except_null().items():
        if k == 'nickname':
            conditions.append(getattr(UserProfile, k).ilike(f'%{v}%'))
        else:
            conditions.append(getattr(UserProfile, k) == v)

    user_profiles: List[UserProfile] = await crud_profile.list(
        conditions=tuple(conditions),
        options=[selectinload(UserProfile.images)]
    )

    result: List[UserProfileSearchResponseS] = []
    for p in user_profiles:
        image_urls = UserProfileImage.get_file_urls(*p.images)
        images = [
            UserProfileSearchImageS(
                id=im.id,
                url=next((u['url'] for u in image_urls if u['id'] == im.id), None),
                type=im.type,
                is_default=im.is_default,
                is_active=im.is_active
            ) for im in p.images
        ]
        result.append(
            UserProfileSearchResponseS(
                id=p.id,
                user_id=p.user_id,
                identity_id=p.identity_id,
                nickname=p.nickname,
                status_message=p.status_message,
                images=images,
                is_default=p.is_default,
                is_active=p.is_active
            )
        )
    return result


@router.post(
    '/relationship/{user_profile_id}/{other_profile_id}',
    dependencies=[Depends(cookie)],
    status_code=status.HTTP_201_CREATED)
async def create_relationship(
    user_profile_id: int,
    other_profile_id: int,
    relation_type: str = Body(embed=True, default=RelationshipType.FRIEND.value),
    user_session: UserSession = Depends(verifier),
    session=Depends(get_async_session)
):
    redis_handler = RedisHandler()
    crud_user_profile = UserProfileCRUD(session)
    crud_relationship = UserRelationshipCRUD(session)

    # 권한 검증
    AuthValidator.get_user_profile(user_session, user_profile_id)

    other_profile: UserProfile = await crud_user_profile.get(
        conditions=(
            UserProfile.id == other_profile_id,
            UserProfile.is_active == 1),
        options=[
            selectinload(UserProfile.images),
            selectinload(UserProfile.followers)
        ])
    other_profile_images: List[UserProfileImage] = other_profile.images
    user_profile: UserProfile = await crud_user_profile.get(
        conditions=(
            UserProfile.id == user_profile_id,
            UserProfile.is_active == 1),
        options=[
            selectinload(UserProfile.followings)
        ])
    relation_type: RelationshipType = RelationshipType(relation_type)
    if not relation_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invalid `relation_type`.')
    if next((
        f for f in user_profile.followings if
        f.other_profile_id == other_profile_id and f.type == relation_type),
        None
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Already following relationship.')

    relationship = await crud_relationship.create(
        my_profile_id=user_profile_id,
        other_profile_id=other_profile_id,
        other_profile_nickname=other_profile.nickname,
        type=relation_type
    )
    await session.commit()
    await session.refresh(relationship)

    # Redis 데이터 추가
    RedisFollowingsByUserProfileS.sadd(
        redis_handler.redis_cluster,
        user_profile_id,
        RedisFollowingsByUserProfileS.schema(
            id=other_profile_id,
            identity_id=other_profile.identity_id,
            nickname=other_profile.get_nickname_by_other(user_profile_id),
            type=relationship.type.name.lower(),
            favorites=relationship.favorites,
            is_hidden=relationship.is_hidden,
            is_forbidden=relationship.is_forbidden,
            files=await redis_handler.generate_files_schema(
                UserProfileImage, [i for i in other_profile_images if i.is_default]
            )
        )
    )

    return UserRelationshipS.from_orm(relationship)


@router.patch('/relationship/{user_profile_id}/{other_profile_id}', dependencies=[Depends(cookie)])
async def update_relationship(
    user_profile_id: int,
    other_profile_id: int,
    data: UserRelationshipUpdateS,
    user_session: UserSession = Depends(verifier),
    session=Depends(get_async_session)
):
    redis_handler = RedisHandler()
    crud = UserRelationshipCRUD(session)

    # 권한 검증
    AuthValidator.get_user_profile(user_session, user_profile_id)

    values = data.values_except_null()
    conditions = (
        UserRelationship.my_profile_id == user_profile_id,
        UserRelationship.other_profile_id == other_profile_id
    )
    await crud.update(conditions=conditions, **values)
    await session.commit()

    following_db: UserRelationship = await crud.get(
        conditions=conditions,
        options=[
            joinedload(UserRelationship.other_profile)
            .selectinload(UserProfile.images)
        ])
    with redis_handler.lock(
        key=RedisFollowingsByUserProfileS.get_lock_key(user_profile_id)
    ):
        followings_redis: List[RedisFollowingByUserProfileS] = (
            RedisFollowingsByUserProfileS.smembers(redis_handler.redis_cluster, user_profile_id)
        )
        duplicated_following_redis: List[RedisFollowingByUserProfileS] = [
            f for f in followings_redis if f.id == other_profile_id
        ]

        if duplicated_following_redis:
            with redis_handler.pipeline() as pipe:
                pipe = RedisFollowingsByUserProfileS.srem(pipe, user_profile_id, *duplicated_following_redis)
                following_redis = duplicated_following_redis[-1]
                for k, v in values.items():
                    if k == UserRelationship.type.key:
                        setattr(following_redis, k, v.name.lower())
                    elif k == UserRelationship.other_profile_nickname.key:
                        setattr(following_redis, 'nickname', v)
                    else:
                        setattr(following_redis, k, v)
                pipe = RedisFollowingsByUserProfileS.sadd(pipe, user_profile_id, following_redis)
                pipe.execute()
        else:
            RedisFollowingsByUserProfileS.sadd(
                redis_handler.redis_cluster,
                user_profile_id,
                RedisFollowingsByUserProfileS.schema(
                    id=other_profile_id,
                    identity_id=following_db.other_profile.identity_id,
                    nickname=following_db.other_profile.nickname,
                    type=following_db.type.name.lower(),
                    favorites=following_db.favorites,
                    is_hidden=following_db.is_hidden,
                    is_forbidden=following_db.is_forbidden,
                    files=await redis_handler.generate_files_schema(
                        UserProfileImage, [i for i in following_db.other_profile.images if i.is_default]
                    )
                )
            )

    return UserRelationshipS.from_orm(following_db)


@router.delete('/relationship/{user_profile_id}/{other_profile_id}', dependencies=[Depends(cookie)])
async def delete_relationship(
    user_profile_id: int,
    other_profile_id: int,
    user_session: UserSession = Depends(verifier),
    session=Depends(get_async_session)
):
    redis_handler = RedisHandler()
    crud = UserRelationshipCRUD(session)

    # 권한 검증
    AuthValidator.get_user_profile(user_session, user_profile_id)

    await crud.delete(
        conditions=(
            UserRelationship.my_profile_id == user_profile_id,
            UserRelationship.other_profile_id == other_profile_id))
    await session.commit()

    followings_redis: List[RedisFollowingByUserProfileS] = (
        RedisFollowingsByUserProfileS.smembers(redis_handler.redis_cluster, user_profile_id)
    )
    duplicated_following_redis: List[RedisFollowingByUserProfileS] = [
        f for f in followings_redis if f.id == other_profile_id
    ]
    if duplicated_following_redis:
        RedisFollowingsByUserProfileS.srem(redis_handler.redis_cluster, user_profile_id, *duplicated_following_redis)

    return {'success': True}


@router.get('/relationship/{user_profile_id}/search', dependencies=[Depends(cookie)])
async def search_relationship(
    user_profile_id: int,
    nickname: Optional[str] = None,
    follow_type: Optional[int] = FollowType.FOLLOWING.value,
    relationship_type: Optional[int] = None,
    favorites: Optional[bool] = None,
    is_hidden: Optional[bool] = False,
    is_forbidden: Optional[bool] = False,
    user_session: UserSession = Depends(verifier),
    session=Depends(get_async_session)
):
    crud_relationship = UserRelationshipCRUD(session)

    # 권한 검증
    profile: UserProfile = AuthValidator.get_user_profile(user_session, user_profile_id)

    request_s = UserRelationshipSearchS(
        nickname=nickname,
        follow_type=follow_type,
        relationship_type=relationship_type,
        favorites=favorites,
        is_hidden=is_hidden,
        is_forbidden=is_forbidden
    )

    conditions = []

    for k, v in request_s.values_except_null().items():
        if isinstance(v, IntValueEnum):
            if isinstance(v, FollowType):
                if v == FollowType.FOLLOWING:
                    conditions.append(UserRelationship.my_profile_id == user_profile_id)
                elif v == FollowType.FOLLOWER:
                    conditions.append(UserRelationship.other_profile_id == user_profile_id)
            else:
                if k == 'relationship_type':
                    conditions.append(UserRelationship.type == v)
                else:
                    conditions.append(getattr(UserRelationship, k) == v)
        elif k == 'nickname':
            continue
        else:
            conditions.append(getattr(UserRelationship, k) == v)

    if not request_s.follow_type:
        conditions.append(or_(
            UserRelationship.my_profile_id == user_profile_id,
            UserRelationship.other_profile_id == user_profile_id
        ))

    if request_s.nickname:
        if request_s.follow_type == FollowType.FOLLOWING:
            conditions.append(
                UserRelationship.other_profile_nickname.ilike(f'%{request_s.nickname}%'),
            )
        elif request_s.follow_type == FollowType.FOLLOWER:
            conditions.append(
                UserRelationship.my_profile.has(UserProfile.nickname.ilike(f'%{request_s.nickname}%')),
            )
        else:
            conditions.append(or_(
                UserRelationship.other_profile_nickname.ilike(f'%{request_s.nickname}%'),
                UserRelationship.my_profile.has(UserProfile.nickname.ilike(f'%{request_s.nickname}%'))
            ))

    relationships: List[UserRelationship] = await crud_relationship.list(
        conditions=tuple(conditions),
        options=[
            joinedload(UserRelationship.my_profile)
            .selectinload(UserProfile.images),
            joinedload(UserRelationship.my_profile)
            .selectinload(UserProfile.followers),
            joinedload(UserRelationship.other_profile)
            .selectinload(UserProfile.images),
            joinedload(UserRelationship.other_profile)
            .selectinload(UserProfile.followers)
        ]
    )

    result: List[UserRelationshipSearchResponseS] = []
    for r in relationships:
        if request_s.follow_type:
            profiles: List[UserProfile] = [
                r.my_profile if request_s.follow_type == FollowType.FOLLOWER
                else r.other_profile
            ]
        else:
            profiles: List[UserProfile] = [r.my_profile, r.other_profile]

        for p in profiles:
            image_urls = UserProfileImage.get_file_urls(*p.images)
            images = [
                UserProfileSearchImageS(
                    id=im.id,
                    url=next((u['url'] for u in image_urls if u['id'] == im.id), None),
                    type=im.type,
                    is_default=im.is_default,
                    is_active=im.is_active
                ) for im in p.images
            ]
            result.append(
                UserRelationshipSearchResponseS(
                    id=r.id,
                    profile=UserProfileSearchResponseS(
                        id=p.id,
                        user_id=p.user_id,
                        identity_id=p.identity_id,
                        nickname=p.get_nickname_by_other(profile.id),
                        status_message=p.status_message,
                        images=images,
                        is_default=p.is_default,
                        is_active=p.is_active
                    ),
                    type=r.type,
                    favorites=r.favorites,
                    is_hidden=r.is_hidden,
                    is_forbidden=r.is_forbidden
                )
            )
    return result
