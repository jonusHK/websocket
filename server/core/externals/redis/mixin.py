import datetime
import json
from json import JSONDecodeError
from typing import Any, TypeVar, Mapping, Sequence, Optional

from rediscluster import RedisCluster, ClusterPipeline

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


class DeleteMixin:
    @classmethod
    def delete(cls, redis: RedisCluster, *key_param):
        assert hasattr(cls, 'get_key'), 'Must have `KeyMixin` class.'
        keys = [getattr(cls, 'get_key')(k) for k in key_param]
        return redis.delete(*keys)


class ConvertFormatMixin:
    @classmethod
    def decode(cls, value: Any):
        if not value:
            return value
        elif isinstance(value, list | tuple | set):
            decoded = [cls.decode(v) for v in value]
            return decoded
        elif isinstance(value, bytes):
            return value.decode('utf-8')
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


class SetCollectionMixin(KeyMixin, ValueMixin, ConvertFormatMixin, DeleteMixin):
    @classmethod
    def sadd(cls, redis: RedisCluster, key_param: Any | None, *args):
        key = cls.get_key(key_param)
        args = cls.get_value(args)
        return redis.sadd(key, *args)

    @classmethod
    def smembers(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        result = redis.smembers(key)
        result = cls.decode(result)
        return cls.to_schema(result) or []

    @classmethod
    def srem(cls, redis: RedisCluster, key_param: Any | None, *args):
        key = cls.get_key(key_param)
        args = cls.get_value(args)
        return redis.srem(key, *args)

    @classmethod
    def scard(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        return redis.scard(key)

    @classmethod
    def sismember(cls, redis: RedisCluster, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        redis.sismember(key, value)


class ListCollectionMixin(KeyMixin, ValueMixin, ConvertFormatMixin, DeleteMixin):
    @classmethod
    def lpush(cls, redis: RedisCluster, key_param: Any | None, *args):
        key = cls.get_key(key_param)
        args = cls.get_value(args)
        return redis.lpush(key, *args)

    @classmethod
    def rpush(cls, redis: RedisCluster, key_param: Any | None, *args):
        key = cls.get_key(key_param)
        args = cls.get_value(args)
        return redis.rpush(key, *args)

    @classmethod
    def lpop(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        res = redis.lpop(key)
        if not isinstance(res, ClusterPipeline):
            result = cls.decode(redis.lpop(key))
            return cls.to_schema(result)
        return res

    @classmethod
    def rpop(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        res = redis.rpop(key)
        if not isinstance(res, ClusterPipeline):
            result = cls.decode(redis.rpop(key))
            return cls.to_schema(result)
        return res

    @classmethod
    def lrange(cls, redis: RedisCluster, key_param: Any | None, start: int = 0, stop: int = -1):
        key = cls.get_key(key_param)
        result = redis.lrange(key, start, stop)
        result = cls.decode(result)
        return cls.to_schema(result)

    @classmethod
    def lindex(cls, redis: RedisCluster, key_param: Any | None, index: int):
        key = cls.get_key(key_param)
        return redis.lindex(key, index)

    @classmethod
    def lset(cls, redis: RedisCluster, key_param: Any | None, index: int, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return redis.lset(key, index, value)

    @classmethod
    def lrem(cls, redis: RedisCluster, key_param: Any | None, value: Any, count: int = 0):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return redis.lrem(key, count, value)

    @classmethod
    def llen(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        return redis.llen(key)

    @classmethod
    def ltrim(cls, redis: RedisCluster, key_param: Any | None, start: int, end: int):
        key = cls.get_key(key_param)
        return redis.ltrim(key, start, end)


class StringCollectionMixin(KeyMixin, ValueMixin, ConvertFormatMixin, DeleteMixin):
    @classmethod
    def set(cls, redis: RedisCluster, key_param: Any | None, value: Any, **kwargs):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return redis.set(key, value, **kwargs)

    @classmethod
    def setex(cls, redis: RedisCluster, key_param: Any | None, time: int, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return redis.setex(key, time, value)

    @classmethod
    def setnx(cls, redis: RedisCluster, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return redis.setnx(key, value)

    @classmethod
    def strlen(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        return redis.strlen(key)

    @classmethod
    def setrange(cls, redis: RedisCluster, key_param: Any | None, offset: int, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return redis.setrange(key, offset, value)

    @classmethod
    def get(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        result = cls.decode(redis.get(key))
        return cls.to_schema(result)

    @classmethod
    def getrange(cls, redis: RedisCluster, key_param: Any | None, start: int = 0, end: int = -1):
        key = cls.get_key(key_param)
        result = cls.decode(redis.getrange(key, start, end))
        return cls.to_schema(result)

    @classmethod
    def incr(cls, redis: RedisCluster, key_param: Any | None, amount: int = 1):
        key = cls.get_key(key_param)
        return redis.incr(key, amount)

    @classmethod
    def decr(cls, redis: RedisCluster, key_param: Any | None, amount: int = 1):
        key = cls.get_key(key_param)
        return redis.decr(key, amount)

    @classmethod
    def incrbyfloat(cls, redis: RedisCluster, key_param: Any | None, amount: float):
        key = cls.get_key(key_param)
        return redis.incrbyfloat(key, amount)

    @classmethod
    def mset(cls, redis: RedisCluster, mapping: Mapping[AnyKeyT, Any]):
        return redis.mset(mapping=mapping)

    @classmethod
    def mget(cls, redis: RedisCluster, keys: KeyT | Sequence[KeyT], *args):
        args = cls.get_value(args)
        result = cls.decode(redis.mget(keys, *args))
        return cls.to_schema(result)

    @classmethod
    def msetnx(cls, redis: RedisCluster, mapping: Mapping[AnyKeyT, EncodableT]):
        return redis.msetnx(mapping)

    @classmethod
    def psetex(cls, redis: RedisCluster, key_param: Any | None, time_ms: ExpiryT, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return redis.psetex(key, time_ms, value)

    @classmethod
    def getset(cls, redis: RedisCluster, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        res = redis.getset(key, value)
        if not isinstance(res, ClusterPipeline):
            result = cls.decode(redis.getset(key, value))
            return cls.to_schema(result)
        return res

    @classmethod
    def append(cls, redis: RedisCluster, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return redis.append(key, value)


class SortedSetCollectionMixin(KeyMixin, ValueMixin, ConvertFormatMixin, DeleteMixin):
    @classmethod
    def zadd(cls, redis: RedisCluster, key_param: Any | None, data: Any, **kwargs):
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
        return redis.zadd(key, convert_mapping, **kwargs)

    @classmethod
    def zscore(cls, redis: RedisCluster, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return redis.zscore(key, value)

    @classmethod
    def zrank(cls, redis: RedisCluster, key_param: Any | None, value: Any):
        key = cls.get_key(key_param)
        value = cls.get_value(value)
        return redis.zrank(key, value)

    @classmethod
    def zrange(cls, redis: RedisCluster, key_param: Any | None, start: int = 0, end: int = -1, **kwargs):
        key = cls.get_key(key_param)
        result = cls.decode(redis.zrange(key, start, end, **kwargs))
        return cls.to_schema(result)

    @classmethod
    def zrevrange(cls, redis: RedisCluster, key_param: Any | None, start: int = 0, end: int = -1, **kwargs):
        key = cls.get_key(key_param)
        result = cls.decode(redis.zrevrange(key, start, end, **kwargs))
        return cls.to_schema(result)

    @classmethod
    def zrangebyscore(cls, redis: RedisCluster, key_param: Any | None, _min: ZScoreBoundT, _max: ZScoreBoundT, **kwargs):
        key = cls.get_key(key_param)
        result = cls.decode(redis.zrangebyscore(key, _min, _max, **kwargs))
        return cls.to_schema(result)

    @classmethod
    def zcount(cls, redis: RedisCluster, key_param: Any | None, _min: ZScoreBoundT, _max: ZScoreBoundT):
        key = cls.get_key(key_param)
        return redis.zcount(key, _min, _max)

    @classmethod
    def zrem(cls, redis: RedisCluster, key_param: Any | None, *values):
        key = cls.get_key(key_param)
        values = cls.get_value(values)
        return redis.zrem(key, *values)

    @classmethod
    def zcard(cls, redis: RedisCluster, key_param: Any | None):
        key = cls.get_key(key_param)
        return redis.zcard(key)
