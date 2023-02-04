from typing import List

from fastapi import APIRouter

from server.api import ExceptionHandlerRoute
from server.core.externals.redis import AioRedis
from server.core.externals.redis.schemas import RedisUserProfilesByRoomS, RedisChatRoomsByUserProfileS, \
    RedisChatHistoriesByRoomS, RedisFollowingsByUserProfileS, RedisChatRoomsInfoS, RedisChatRoomInfoS

router = APIRouter(route_class=ExceptionHandlerRoute)

redis = AioRedis().redis


@router.get('/rooms')
async def chat_rooms():
    return await RedisChatRoomsInfoS.smembers(redis, None)


@router.get('/rooms/{room_id}')
async def chat_rooms_by_id(room_id: int):
    rooms: List[RedisChatRoomInfoS] = await RedisChatRoomsInfoS.smembers(redis, None)
    return next((room for room in rooms if room.id == room_id), None)


@router.get('/rooms/user_profile/{user_profile_id}')
async def chat_rooms_by_user_profile(user_profile_id: int):
    return await RedisChatRoomsByUserProfileS.zrange(redis, user_profile_id)


@router.get('/user_profiles/{room_id}/{user_profile_id}')
async def user_profiles_by_room(room_id: int, user_profile_id: int):
    return await RedisUserProfilesByRoomS.smembers(redis, (room_id, user_profile_id))


@router.get('/chats/{room_id}')
async def chat_histories_by_room(room_id: int):
    return await RedisChatHistoriesByRoomS.zrange(redis, room_id)


@router.get('/followings/{user_profile_id}')
async def followings_by_user_profile(user_profile_id: int):
    return await RedisFollowingsByUserProfileS.smembers(redis, user_profile_id)
