from typing import List

from fastapi import APIRouter

from server.api import ExceptionHandlerRoute
from server.api.common import RedisHandler
from server.core.externals.redis.schemas import (
    RedisUserProfilesByRoomS, RedisChatRoomsByUserProfileS, RedisChatHistoriesByRoomS,
    RedisFollowingsByUserProfileS, RedisChatRoomsInfoS, RedisChatRoomInfoS
)

router = APIRouter(route_class=ExceptionHandlerRoute)

redis_handler = RedisHandler()


@router.get('/rooms')
async def chat_rooms():
    return RedisChatRoomsInfoS.smembers(redis_handler.redis, None)


@router.get('/rooms/{room_id}')
async def chat_rooms_by_id(room_id: int):
    rooms: List[RedisChatRoomInfoS] = RedisChatRoomsInfoS.smembers(redis_handler.redis, None)
    return next((room for room in rooms if room.id == room_id), None)


@router.get('/rooms/user_profile/{user_profile_id}')
async def chat_rooms_by_user_profile(user_profile_id: int):
    return RedisChatRoomsByUserProfileS.zrange(redis_handler.redis, user_profile_id)


@router.get('/user_profiles/{room_id}/{user_profile_id}')
async def user_profiles_by_room(room_id: int, user_profile_id: int):
    return RedisUserProfilesByRoomS.smembers(redis_handler.redis, (room_id, user_profile_id))


@router.get('/chats/{room_id}')
async def chat_histories_by_room(room_id: int):
    return RedisChatHistoriesByRoomS.zrange(redis_handler.redis, room_id)


@router.get('/followings/{user_profile_id}')
async def followings_by_user_profile(user_profile_id: int):
    return RedisFollowingsByUserProfileS.smembers(redis_handler.redis, user_profile_id)
