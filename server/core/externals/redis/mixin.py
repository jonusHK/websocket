import datetime
import json
from json import JSONDecodeError
from typing import Any, TypeVar, Mapping, Sequence, Optional, Awaitable

from aioredis_cluster import RedisCluster
from aioredis_cluster._aioredis.commands import Pipeline

KeyT = bytes | str | memoryview
EncodedT = bytes | memoryview
DecodedT = str | int | float
EncodableT = EncodedT | DecodedT
ExpiryT = int | datetime.timedelta
ZScoreBoundT = float | int
AnyKeyT = TypeVar("AnyKeyT", bytes, str, memoryview)


class KeyMixin:
    @classmethod
    def get_key(cls, key_param: Optional[Any] = None):
        if not key_param:
            return getattr(cls, 'format')
        elif isinstance(key_param, list | tuple):
            return getattr(cls, 'format').format(*key_param)
        return getattr(cls, 'format').format(key_param)

    @classmethod
    def get_lock_key(cls, key_param: Optional[Any] = None):
        return f'lock:{cls.get_key(key_param)}'


class ValueMixin:
    @classmethod
    def get_value(cls, value: Any):
        if isinstance(value, EncodableT):
            return value
        elif isinstance(value, list | tuple):
            return [cls.get_value(v) for v in value]
        elif isinstance(value, getattr(cls, 'schema')):
            return value.json()
        return json.dumps(value)


class TransactionMixin:
    @classmethod
    async def execute(cls, target: Awaitable):
        return target if isinstance(target, Pipeline) else await target


class DeleteMixin:
    @classmethod
    async def delete(cls, redis: RedisCluster | Pipeline, *key_param):
        assert hasattr(cls, 'get_key'), 'Must have `KeyMixin` class.'
        keys = [getattr(cls, 'get_key')(k) for k in key_param]
        return await getattr(cls, 'execute')(redis.delete(*keys))


class ConvertFormatMixin:
    @classmethod
    def decode(cls, value: Any):
        if not value:
            return value
        elif isinstance(value, list | tuple | set):
            decoded = [cls.decode(v) for v in value]
            return decoded
        elif isinstance(value, bytes):
            return cls.decode(value.decode('utf-8'))
        try:
            return json.loads(value)
        except (JSONDecodeError, TypeError):
            return value

    @classmethod
    def to_schema(cls, target: Any):
        if not target:
            return target
        elif isinstance(target, list):
            return [getattr(cls, 'schema')(**obj) for obj in target]
        elif isinstance(target, dict):
            return getattr(cls, 'schema')(**target)
        raise AssertionError('Type should be `list` or `dict`.')


class SetCollectionMixin(KeyMixin, ValueMixin, TransactionMixin, ConvertFormatMixin, DeleteMixin):
    @classmethod
    async def sadd(cls, redis: RedisCluster | Pipeline, key_param: Any | None, *args):
        key = cls.get_key(key_param)
        args = cls.get_value(args)
        return await cls.execute(redis.sadd(key, *args))

    @classmethod
    async def smembers(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        result = await redis.smembers(key)
        result = cls.decode(result)
        return cls.to_schema(result) or []

    @classmethod
    async def srem(cls, redis: RedisCluster | Pipeline, key_param: Any | None, *args):
        key = cls.get_key(key_param)
        args = cls.get_value(args)
        return await cls.execute(redis.srem(key, *args))

    @classmethod
    async def scard(cls, redis: RedisCluster | Pipeline, key_param: Any | None):
        key = cls.get_key(key_param)
        return await cls.execute(redis.scard(key))

    @classmethod
    async def sismember(cls, redis: RedisCluster, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.sismember(key, value)


class ListCollectionMixin(KeyMixin, ValueMixin, TransactionMixin, ConvertFormatMixin, DeleteMixin):
    @classmethod
    async def lpush(cls, redis: RedisCluster | Pipeline, key_param: Any | None, *args):
        key = cls.get_key(key_param)
        args = cls.get_value(args)
        return await cls.execute(redis.lpush(key, *args))

    @classmethod
    async def rpush(cls, redis: RedisCluster | Pipeline, key_param: Any | None, *args):
        key = cls.get_key(key_param)
        args = cls.get_value(args)
        return await cls.execute(redis.rpush(key, *args))

    @classmethod
    async def lpop(cls, redis: RedisCluster | Pipeline, key_param: Any | None):
        key = cls.get_key(key_param)
        res = await cls.execute(redis.lpop(key))
        if isinstance(res, RedisCluster):
            result = cls.decode(res)
            return cls.to_schema(result)
        return res

    @classmethod
    async def rpop(cls, redis: RedisCluster | Pipeline, key_param: Any | None):
        key = cls.get_key(key_param)
        res = await cls.execute(redis.rpop(key))
        if isinstance(res, RedisCluster):
            result = cls.decode(res)
            return cls.to_schema(result)
        return res

    @classmethod
    async def lrange(cls, redis: RedisCluster, key_param: Any | None, start: int = 0, stop: int = -1):
        key = cls.get_key(key_param)
        result = await redis.lrange(key, start, stop)
        result = cls.decode(result)
        return cls.to_schema(result)

    @classmethod
    async def lindex(cls, redis: RedisCluster, key_param: Any | None, index: int):
        key = cls.get_key(key_param)
        return await redis.lindex(key, index)

    @classmethod
    async def lset(cls, redis: RedisCluster | Pipeline, key_param: Any | None, index: int, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await cls.execute(redis.lset(key, index, value))

    @classmethod
    async def lrem(cls, redis: RedisCluster | Pipeline, key_param: Any | None, value: Any, count: int = 0):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await cls.execute(redis.lrem(key, count, value))

    @classmethod
    async def llen(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        return await redis.llen(key)

    @classmethod
    async def ltrim(cls, redis: RedisCluster | Pipeline, key_param: Any | None, start: int, end: int):
        key = cls.get_key(key_param)
        return await cls.execute(redis.ltrim(key, start, end))


class StringCollectionMixin(KeyMixin, ValueMixin, TransactionMixin, ConvertFormatMixin, DeleteMixin):
    @classmethod
    async def set(cls, redis: RedisCluster | Pipeline, key_param: Any | None, value: Any, **kwargs):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await cls.execute(redis.set(key, value, **kwargs))

    @classmethod
    async def setex(cls, redis: RedisCluster | Pipeline, key_param: Any | None, time: int, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await cls.execute(redis.setex(key, time, value))

    @classmethod
    async def setnx(cls, redis: RedisCluster | Pipeline, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await cls.execute(redis.setnx(key, value))

    @classmethod
    async def strlen(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        return await redis.strlen(key)

    @classmethod
    async def setrange(cls, redis: RedisCluster, key_param: Any | None, offset: int, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.setrange(key, offset, value)

    @classmethod
    async def get(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.get(key))
        return cls.to_schema(result)

    @classmethod
    async def getrange(cls, redis: RedisCluster, key_param: Any | None, start: int = 0, end: int = -1):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.getrange(key, start, end))
        return cls.to_schema(result)

    @classmethod
    async def incr(cls, redis: RedisCluster | Pipeline, key_param: Any | None):
        key = cls.get_key(key_param)
        return await cls.execute(redis.incr(key))

    @classmethod
    async def decr(cls, redis: RedisCluster | Pipeline, key_param: Any | None):
        key = cls.get_key(key_param)
        return await cls.execute(redis.decr(key))

    @classmethod
    async def incrbyfloat(cls, redis: RedisCluster | Pipeline, key_param: Any | None, amount: float):
        key = cls.get_key(key_param)
        return await cls.execute(redis.incrbyfloat(key, amount))

    @classmethod
    async def mset(cls, redis: RedisCluster | Pipeline, mapping: Mapping[AnyKeyT, Any]):
        return await cls.execute(redis.mset(mapping))

    @classmethod
    async def mget(cls, redis: RedisCluster, keys: KeyT | Sequence[KeyT], *args):
        args = cls.get_value(args)
        result = cls.decode(await redis.mget(keys, *args))
        return cls.to_schema(result)

    @classmethod
    async def psetex(cls, redis: RedisCluster | Pipeline, key_param: Any | None, time_ms: ExpiryT, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await cls.execute(redis.psetex(key, time_ms, value))

    @classmethod
    async def getset(cls, redis: RedisCluster | Pipeline, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        res = await cls.execute(redis.getset(key, value))
        if isinstance(res, RedisCluster):
            result = cls.decode(res)
            return cls.to_schema(result)
        return res

    @classmethod
    async def append(cls, redis: RedisCluster | Pipeline, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await cls.execute(redis.append(key, value))


class SortedSetCollectionMixin(KeyMixin, ValueMixin, TransactionMixin, ConvertFormatMixin, DeleteMixin):
    @classmethod
    async def zadd(cls, redis: RedisCluster | Pipeline, key_param: Any | None, data: Any, **kwargs):
        key = cls.get_key(key_param)
        convert_mapping = {}
        if isinstance(data, Mapping):
            for pair in data.items():
                convert_mapping[cls.get_value(pair[0])] = cls.get_value(pair[1])
        elif isinstance(data, list | tuple | getattr(cls, 'schema')):
            if isinstance(data, list | tuple):
                for obj in data:
                    assert isinstance(obj, getattr(cls, 'schema')), (
                        f"Should be instance of {getattr(cls, 'schema').__name__}"
                    )
                    convert_mapping[cls.get_value(obj)] = getattr(obj, getattr(cls, 'score'))
            else:
                convert_mapping[cls.get_value(data)] = getattr(data, getattr(cls, 'score'))
        return await cls.execute(redis.zadd(key, convert_mapping, **kwargs))

    @classmethod
    async def zscore(cls, redis: RedisCluster, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.zscore(key, value)

    @classmethod
    async def zrank(cls, redis: RedisCluster, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return await redis.zrank(key, value)

    @classmethod
    async def zrange(cls, redis: RedisCluster, key_param: Any | None, start: int = 0, end: int = -1, **kwargs):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.zrange(key, start, end, **kwargs))
        return cls.to_schema(result)

    @classmethod
    async def zrevrange(cls, redis: RedisCluster, key_param: Any | None, start: int = 0, end: int = -1, **kwargs):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.zrevrange(key, start, end, **kwargs))
        return cls.to_schema(result)

    @classmethod
    async def zrangebyscore(cls, redis: RedisCluster, key_param: Any | None, _min: ZScoreBoundT, _max: ZScoreBoundT, **kwargs):
        key = cls.get_key(key_param)
        result = cls.decode(await redis.zrangebyscore(key, _min, _max, **kwargs))
        return cls.to_schema(result)

    @classmethod
    async def zcount(cls, redis: RedisCluster, key_param: Any | None, _min: ZScoreBoundT, _max: ZScoreBoundT):
        key = cls.get_key(key_param)
        return await redis.zcount(key, _min, _max)

    @classmethod
    async def zrem(cls, redis: RedisCluster | Pipeline, key_param: Any | None, *values):
        key = cls.get_key(key_param)
        values = cls.get_value(values)
        return await cls.execute(redis.zrem(key, *values))

    @classmethod
    async def zcard(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        return await redis.zcard(key)
