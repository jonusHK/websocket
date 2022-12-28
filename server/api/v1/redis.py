from fastapi import APIRouter

from server.api import ExceptionHandlerRoute
from server.core.externals.redis import AioRedis
from server.core.externals.redis.schemas import RedisUserProfilesByRoomS, RedisChatRoomsByUserProfileS, \
    RedisChatHistoriesByRoomS, RedisFollowingsByUserProfileS

router = APIRouter(route_class=ExceptionHandlerRoute)

redis = AioRedis().redis


@router.get("/user_profiles")
async def user_profiles_by_room(room_id: int, user_profile_id: int):
    return await RedisUserProfilesByRoomS.smembers(redis, (room_id, user_profile_id))


@router.get("/rooms")
async def chat_rooms_by_user_profile(user_profile_id: int):
    return await RedisChatRoomsByUserProfileS.zrange(redis, user_profile_id)


@router.get("/chats")
async def chat_histories_by_room(room_id: int):
    return await RedisChatHistoriesByRoomS.zrange(redis, room_id)


@router.get("/followings")
async def followings_by_user_profile(user_profile_id: int):
    return await RedisFollowingsByUserProfileS.smembers(redis, user_profile_id)
