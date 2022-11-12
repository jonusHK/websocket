import datetime
import json
from typing import Any, TypeVar, Mapping, Sequence

from aioredis import Redis


KeyT = bytes | str | memoryview
EncodedT = bytes | memoryview
DecodedT = str | int | float
EncodableT = EncodedT | DecodedT
ExpiryT = int | datetime.timedelta
AnyKeyT = TypeVar("AnyKeyT", bytes, str, memoryview)


class ListCollectionMixin:
    def lpush(self, redis: Redis, key_param: tuple[Any], *args):
        key: KeyT = getattr(self, 'format').format(*key_param)
        args = [
            json.dumps(arg) if not isinstance(arg, EncodableT)
            else arg for arg in args]
        return await redis.lpush(key, *args)

    def rpush(self, redis: Redis, key_param: tuple[Any], *args):
        key = getattr(self, 'format').format(*key_param)
        args = [
            json.dumps(arg) if not isinstance(arg, EncodableT)
            else arg for arg in args]
        return await redis.rpush(key, *args)

    def lpop(self, redis: Redis, key_param: tuple[Any]):
        key = getattr(self, 'format').format(*key_param)
        return await redis.lpop(key)

    def rpop(self, redis: Redis, key_param: tuple[Any]):
        key = getattr(self, 'format').format(*key_param)
        return await redis.rpop(key)

    def lrange(self, redis: Redis, key_param: tuple[Any], start: int = 0, stop: int = -1):
        key = getattr(self, 'format').format(*key_param)
        return await redis.lrange(key, start, stop)


class StringCollectionMixin:
    def set(self, redis: Redis, key_param: tuple[Any], value: Any, **kwargs):
        key = getattr(self, 'format').format(*key_param)
        value = json.dumps(value) if isinstance(value, EncodableT) else value
        return await redis.set(key, value, **kwargs)

    def setex(self, redis: Redis, key_param: tuple[Any], time: int, value: Any):
        key = getattr(self, 'format').format(*key_param)
        value = json.dumps(value) if isinstance(value, EncodableT) else value
        return await redis.setex(key, time, value)

    def setnx(self, redis: Redis, key_param: tuple[Any], value: Any):
        key = getattr(self, 'format').format(*key_param)
        value = json.dumps(value) if isinstance(value, EncodableT) else value
        return await redis.setnx(key, value)

    def strlen(self, redis: Redis, key_param: tuple[Any]):
        key = getattr(self, 'format').format(*key_param)
        return await redis.strlen(key)

    def setrange(self, redis: Redis, key_param: tuple[Any], offset: int, value: Any):
        key = getattr(self, 'format').format(*key_param)
        value = json.dumps(value) if isinstance(value, EncodableT) else value
        return await redis.setrange(key, offset, value)

    def getrange(self, redis: Redis, key_param: tuple[Any], start: int = 0, end: int = -1):
        key = getattr(self, 'format').format(*key_param)
        return await redis.getrange(key, start, end)

    def incr(self, redis: Redis, key_param: tuple[Any], amount: int = 1):
        key = getattr(self, 'format').format(*key_param)
        return await redis.incr(key, amount)

    def decr(self, redis: Redis, key_param: tuple[Any], amount: int = 1):
        key = getattr(self, 'format').format(*key_param)
        return await redis.decr(key, amount)

    def incrbyfloat(self, redis: Redis, key_param: tuple[Any], amount: float):
        key = getattr(self, 'format').format(*key_param)
        return await redis.incrbyfloat(key, amount)

    def mset(self, redis: Redis, mapping: Mapping[AnyKeyT, EncodableT]):
        return await redis.mset(mapping=mapping)

    def mget(self, redis: Redis, keys: KeyT | Sequence[KeyT], *args):
        args = [
            json.dumps(arg) if not isinstance(arg, EncodableT)
            else arg for arg in args]
        return await redis.mget(keys, *args)

    def msetnx(self, redis: Redis, mapping: Mapping[AnyKeyT, EncodableT]):
        return await redis.msetnx(mapping)

    def psetex(self, redis: Redis, key_param: tuple[Any], time_ms: ExpiryT, value: Any):
        key = getattr(self, 'format').format(*key_param)
        value = json.dumps(value) if isinstance(value, EncodableT) else value
        return await redis.psetex(key, time_ms, value)

    def getset(self, redis: Redis, key_param: tuple[Any], value: Any):
        key = getattr(self, 'format').format(*key_param)
        value = json.dumps(value) if isinstance(value, EncodableT) else value
        return await redis.getset(key, value)

    def append(self, redis: Redis, key_param: tuple[Any], value: Any):
        key = getattr(self, 'format').format(*key_param)
        value = json.dumps(value) if isinstance(value, EncodableT) else value
        return await redis.append(key, value)
