import asyncio
import threading
import time
import uuid
from types import SimpleNamespace
from typing import Optional, Awaitable, NoReturn

from aioredis_cluster import RedisCluster
from redis.client import Redis
from redis.exceptions import RedisError, LockError, LockNotOwnedError


class MultipleRedlockException(Exception):
    def __init__(self, errors, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors = errors

    def __str__(self):
        return ' :: '.join([str(f'{e.__class__.__name__}: {e}') for e in self.errors])

    def __repr__(self):
        return self.__str__()


class Redlock:

    clock_drift_factor = 0.01
    LUA_UNLOCK_SCRIPT = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
    """

    def __init__(
        self,
        redis,
        name: str | bytes | memoryview,
        timeout: int = 1000,  # 1000 milliseconds
        retry_count: int = 3,
        retry_delay: float = 0.2  # 0.2 seconds
    ):
        self.redis = redis
        self.name = name
        self.nodes = self.redis.connection_pool.nodes
        self.timeout = timeout
        self.drift = int(self.clock_drift_factor * self.timeout) + 2
        self.retry_count = retry_count
        self.retry_delay = retry_delay

    @classmethod
    def native_str(cls, x):
        return x if not x or isinstance(x, str) else x.encode('utf-8', 'replace')

    def lock(self):
        lock_value = str(uuid.uuid4())
        quorum = len(self.nodes.nodes) // 2 + 1

        for i in range(self.retry_count):
            n = 0
            start_time = int(time.time() * 1000)
            for node in self.nodes.nodes.values():
                try:
                    r: Redis = self.nodes.get_redis_link(
                        host=node['host'],
                        port=node['port'],
                        decode_responses=True
                    )
                    if r.execute_command('SET', self.name, lock_value, 'NX', 'PX', self.timeout):
                        n += 1
                except RedisError:
                    pass

            elapsed_time = int(time.time() * 1000) - start_time
            validity = int(self.timeout - elapsed_time - self.drift)
            if validity > 0 and n >= quorum:
                return lock_value
            else:
                self.unlock(lock_value)
                time.sleep(self.retry_delay)

        return False

    def unlock(self, value):
        for node in self.nodes.nodes.values():
            try:
                r: Redis = self.nodes.get_redis_link(host=node['host'], port=node['port'], decode_responses=True)
                r.eval(self.LUA_UNLOCK_SCRIPT, 1, self.name, value)
            except RedisError:
                pass


class AioRedisClusterLock:

    LUA_RELEASE_SCRIPT = """
        local token = redis.call('get', KEYS[1])
        if not token or token ~= ARGV[1] then
            return 0
        end
        redis.call('del', KEYS[1])
        return 1
    """

    def __init__(
        self,
        redis: RedisCluster,
        name: str | bytes | memoryview,
        timeout: int = 5,  # 5 seconds
        retry_delay: float = 0.1,  # 0.1 seconds
        blocking: bool = True,
        blocking_timeout: Optional[float] = None,
        thread_local: bool = True
    ):
        self.redis = redis
        self.name = name
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.blocking = blocking
        self.blocking_timeout = blocking_timeout
        self.thread_local = thread_local
        self.local = threading.local() if self.thread_local else SimpleNamespace()
        self.local.token = None

    async def __aenter__(self):
        if await self.acquire():
            return self
        raise LockError('Unable to acquire lock.')

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.release()

    async def acquire(
        self,
        blocking: Optional[bool] = None,
        blocking_timeout: Optional[float] = None,
    ):
        loop = asyncio.get_event_loop()
        token = uuid.uuid1().hex.encode()

        if blocking is None:
            blocking = self.blocking
        if blocking_timeout is None:
            blocking_timeout = self.blocking_timeout
        stop_trying_at = None
        if blocking_timeout is not None:
            stop_trying_at = loop.time() + blocking_timeout

        while True:
            if await self.do_acquire(token):
                self.local.token = token
                return True

            if not blocking:
                return False

            next_try_at = loop.time() + self.retry_delay
            if stop_trying_at is not None and next_try_at > stop_trying_at:
                return False

            await asyncio.sleep(self.retry_delay)

    async def do_acquire(self, token: str | bytes) -> bool:
        if self.timeout:
            timeout = int(self.timeout * 1000)
        else:
            timeout = None

        if await self.redis.set(self.name, token, exist=self.redis.SET_IF_NOT_EXIST, pexpire=timeout):
            return True

        return False

    def release(self) -> Awaitable[NoReturn]:
        token = self.local.token
        if token is None:
            raise LockError('Cannot release an unlocked lock')

        self.local.token = None
        return self.do_release(token)

    async def do_release(self, token: bytes):
        if not bool(
            await self.redis.eval(self.LUA_RELEASE_SCRIPT, keys=[self.name], args=[token])
        ):
            raise LockNotOwnedError(f"Cannot release a lock that's no longer owned")
