import logging
import time
import uuid

from redis.exceptions import RedisError, ResponseError

logger = logging.getLogger('websocket')


class MultipleRedlockException(Exception):
    def __init__(self, errors, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors = errors

    def __str__(self):
        return ' :: '.join([str(f'{e.__class__.__name__}: {e}') for e in self.errors])

    def __repr__(self):
        return self.__str__()


class Redlock:
    default_retry_count = 3
    default_retry_delay = 0.2
    default_ttl = 1000
    clock_drift_factor = 0.01

    def __init__(
        self,
        redis,
        key,
        ttl=default_ttl,
        retry_count=default_retry_count,
        retry_delay=default_retry_delay
    ):
        self.redis = redis
        self.nodes = self.redis.connection_pool.nodes
        self.key = key
        self.ttl = ttl
        self.drift = int(self.clock_drift_factor * self.ttl) + 2
        self.retry_count = retry_count
        self.retry_delay = retry_delay

    @classmethod
    def native_str(cls, x):
        return x if not x or isinstance(x, str) else x.encode('utf-8', 'replace')

    def lock(self):
        lock_value = str(uuid.uuid4())

        for _ in range(self.retry_count):
            n = 0
            start_time = int(time.time() * 1000)
            for node in self.nodes.nodes.values():
                try:
                    r = self.nodes.get_redis_link(host=node['host'], port=node['port'], decode_responses=True)
                    if r.execute_command('SET', self.key, lock_value, 'NX', 'PX', self.ttl):
                        n += 1
                        break
                except RedisError:
                    self.nodes.initialize()

            elapsed_time = int(time.time() * 1000) - start_time
            validity = int(self.ttl - elapsed_time - self.drift)
            if validity > 0 and n >= 1:
                return True
            else:
                self.unlock()
                time.sleep(self.retry_delay)

        return False

    def unlock(self):
        for node in self.nodes.nodes.values():
            try:
                r = self.nodes.get_redis_link(host=node['host'], port=node['port'], decode_responses=True)
                r.execute_command('DEL', self.key)
            except RedisError:
                pass
