import datetime
import json
from json import JSONDecodeError
from typing import Any, TypeVar, Mapping, Sequence, Dict

from aioredis import Redis

KeyT = bytes | str | memoryview
EncodedT = bytes | memoryview
DecodedT = str | int | float
EncodableT = EncodedT | DecodedT
ExpiryT = int | datetime.timedelta
ZScoreBoundT = float | int
AnyKeyT = TypeVar("AnyKeyT", bytes, str, memoryview)


class KeyMixin:
    @classmethod
    def get_key(cls, key_param: Any):
        if isinstance(key_param, list | tuple):
            return getattr(cls, 'format').format(*key_param)
        return getattr(cls, 'format').format(key_param)


class ValueMixin:
    @classmethod
    def get_value(cls, value: Any):
        if isinstance(value, EncodableT):
            return value
        elif isinstance(value, list | tuple):
            copied = [cls.get_value(v) for v in value]
            if isinstance(value, tuple):
                copied = tuple(copied)
            return copied
        elif isinstance(value, getattr(cls, 'schema')):
            return value.json()
        return json.dumps(value)


class ConvertFormatMixin:
    @classmethod
    def decode(cls, value: Any):
        if isinstance(value, list | tuple | set):
            decoded = [cls.decode(v) for v in value]
            if isinstance(value, tuple):
                decoded = tuple(decoded)
            elif isinstance(value, set):
                decoded = set(decoded)
            return decoded
        elif isinstance(value, bytes):
            return value.decode('utf-8')
        try:
            return json.loads(value)
        except (JSONDecodeError, TypeError):
            return value

    @classmethod
    def to_schema(cls, target: Any):
        if target is None:
            return target
        elif isinstance(target, list):
            return [getattr(cls, 'schema')(**obj) for obj in target]
        elif isinstance(target, dict):
            return getattr(cls, 'schema')(**target)
        raise AssertionError('Type should be `list` or `dict`.')


class ListCollectionMixin(KeyMixin, ValueMixin, ConvertFormatMixin):
    @classmethod
    async def lpush(cls, redis: Redis, key_param: Any, *args):
        key = cls.get_key(key_param)
        args = cls.get_value(args)
        return await redis.lpush(key, *args)

    @classmethod
    async def rpush(cls, redis: Redis, key_param: Any, *args):
        key = cls.get_key(key_param)
        args = cls.get_value(args)
        return await redis.rpush(key, *args)

    @classmethod
    async def lpop(cls, redis: Redis, key_param: Any):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.lpop(key))
        return cls.to_schema(result)

    @classmethod
    async def rpop(cls, redis: Redis, key_param: Any):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.rpop(key))
        return cls.to_schema(result)

    @classmethod
    async def lrange(cls, redis: Redis, key_param: Any, start: int = 0, stop: int = -1):
        key = cls.get_key(key_param)
        result = await redis.lrange(key, start, stop)
        result = cls.decode(result)
        return cls.to_schema(result)

    @classmethod
    async def lindex(cls, redis: Redis, key_param: Any, index: int):
        key = cls.get_key(key_param)
        return await redis.lindex(key, index)

    @classmethod
    async def lset(cls, redis: Redis, key_param: Any, index: int, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.lset(key, index, value)

    @classmethod
    async def lrem(cls, redis: Redis, key_param: Any, value: Any, count: int = 0):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.lrem(key, count, value)

    @classmethod
    async def llen(cls, redis: Redis, key_param: Any):
        key = cls.get_key(key_param)
        return await redis.llen(key)

    @classmethod
    async def ltrim(cls, redis: Redis, key_param: Any, start: int, end: int):
        key = cls.get_key(key_param)
        return await redis.ltrim(key, start, end)


class StringCollectionMixin(KeyMixin, ValueMixin, ConvertFormatMixin):
    @classmethod
    async def set(cls, redis: Redis, key_param: Any, value: Any, **kwargs):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.set(key, value, **kwargs)

    @classmethod
    async def setex(cls, redis: Redis, key_param: Any, time: int, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.setex(key, time, value)

    @classmethod
    async def setnx(cls, redis: Redis, key_param: Any, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.setnx(key, value)

    @classmethod
    async def strlen(cls, redis: Redis, key_param: Any):
        key = cls.get_key(key_param)
        return await redis.strlen(key)

    @classmethod
    async def setrange(cls, redis: Redis, key_param: Any, offset: int, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.setrange(key, offset, value)

    @classmethod
    async def get(cls, redis: Redis, key_param: Any):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.get(key))
        return cls.to_schema(result)

    @classmethod
    async def getrange(cls, redis: Redis, key_param: Any, start: int = 0, end: int = -1):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.getrange(key, start, end))
        return cls.to_schema(result)


    @classmethod
    async def incr(cls, redis: Redis, key_param: Any, amount: int = 1):
        key = cls.get_key(key_param)
        return await redis.incr(key, amount)

    @classmethod
    async def decr(cls, redis: Redis, key_param: Any, amount: int = 1):
        key = cls.get_key(key_param)
        return await redis.decr(key, amount)

    @classmethod
    async def incrbyfloat(cls, redis: Redis, key_param: Any, amount: float):
        key = cls.get_key(key_param)
        return await redis.incrbyfloat(key, amount)

    @classmethod
    async def mset(cls, redis: Redis, mapping: Mapping[AnyKeyT, Any]):
        return await redis.mset(mapping=mapping)

    @classmethod
    async def mget(cls, redis: Redis, keys: KeyT | Sequence[KeyT], *args):
        args = cls.get_value(args)
        result = cls.decode(await redis.mget(keys, *args))
        return cls.to_schema(result)

    @classmethod
    async def msetnx(cls, redis: Redis, mapping: Mapping[AnyKeyT, EncodableT]):
        return await redis.msetnx(mapping)

    @classmethod
    async def psetex(cls, redis: Redis, key_param: Any, time_ms: ExpiryT, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.psetex(key, time_ms, value)

    @classmethod
    async def getset(cls, redis: Redis, key_param: Any, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        result = cls.decode(await redis.getset(key, value))
        return cls.to_schema(result)

    @classmethod
    async def append(cls, redis: Redis, key_param: Any, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.append(key, value)


class SortedSetCollectionMixin(KeyMixin, ValueMixin, ConvertFormatMixin):
    @classmethod
    async def zadd(cls, redis: Redis, key_param: Any, data: Any, **kwargs):
        key = cls.get_key(key_param)
        convert_mapping = {}
        if isinstance(data, Mapping):
            for pair in data.items():
                convert_mapping[cls.get_value(pair[0])] = cls.get_value(pair[1])
        elif isinstance(data, list | tuple | getattr(cls, 'schema')):
            if isinstance(data, list | tuple):
                for obj in data:
                    assert isinstance(obj, getattr(cls, 'schema')), \
                        f"Should be instance of {getattr(cls, 'schema').__name__}"
                    convert_mapping[cls.get_value(obj)] = getattr(obj, getattr(cls, 'score'))
            else:
                convert_mapping[cls.get_value(data)] = getattr(data, getattr(cls, 'score'))
        return await redis.zadd(key, convert_mapping, **kwargs)

    @classmethod
    async def zscore(cls, redis: Redis, key_param: Any, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.append(key, value)

    @classmethod
    async def zrank(cls, redis: Redis, key_param: Any, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.zrank(key, value)

    @classmethod
    async def zrange(cls, redis: Redis, key_param: Any, start: int = 0, end: int = -1, **kwargs):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.zrange(key, start, end, **kwargs))
        return cls.to_schema(result)

    @classmethod
    async def zrevrange(cls, redis: Redis, key_param: Any, start: int = 0, end: int = -1, **kwargs):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.zrevrange(key, start, end, **kwargs))
        return cls.to_schema(result)

    @classmethod
    async def zrangebyscore(cls, redis: Redis, key_param: Any, _min: ZScoreBoundT, _max: ZScoreBoundT, **kwargs):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.zrangebyscore(key, _min, _max, **kwargs))
        return cls.to_schema(result)

    @classmethod
    async def zcount(cls, redis: Redis, key_param: Any, _min: ZScoreBoundT, _max: ZScoreBoundT):
        key = cls.get_key(key_param)
        return await redis.zcount(key, _min, _max)

    @classmethod
    async def zrem(cls, redis: Redis, key_param: Any, *values):
        key = cls.get_key(key_param)
        values = cls.get_value(values)
        return await redis.zrem(key, *values)

    @classmethod
    async def zcard(cls, redis: Redis, key_param: Any):
        key = cls.get_key(key_param)
        return await redis.zcard(key)
