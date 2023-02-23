from functools import lru_cache
from typing import Optional

import aioredis
import aioredis_cluster
import rediscluster
from aioredis_cluster.typedef import CommandsFactory
import ssl

from server.db.databases import settings


class AioRedis:
    def __init__(
        self,
        endpoint=settings.redis_endpoint,
        db=settings.redis_database,
        encoding="utf-8",
        max_connections=10,
        decode_responses=True
    ):
        assert isinstance(endpoint, str) or isinstance(endpoint, list)
        self.endpoint = endpoint
        self.db = db
        self.encoding = encoding
        self.max_connections = max_connections
        self.decode_responses = decode_responses
        self.redis = aioredis.Redis.from_url(
            'redis://%s' % (self.endpoint[0] if isinstance(endpoint, list) else self.endpoint),
            db=self.db,
            encoding=self.encoding,
            max_connections=self.max_connections,
            decode_responses=self.decode_responses
        )


class AioRedisCluster:
    def __init__(
        self,
        endpoint=settings.redis_endpoint,
        cluster_commands_factory: CommandsFactory = None,
        retry_min_delay: float = None,
        retry_max_delay: float = None,
        max_attempts: int = None,
        attempt_timeout: float = None,
        state_reload_interval: float = None,
        follow_cluster: bool = None,
        idle_connection_timeout: float = None,
        username: str = None,
        password: str = None,
        encoding: str = None,
        pool_minsize: int = None,
        pool_maxsize: int = None,
        connect_timeout: float = None,
        ssl: Optional[bool | ssl.SSLContext] = None,
    ):
        self.endpoint = endpoint
        self.connections = list(map(
            lambda x: {
                'host': x.rsplit(':', 1)[0],
                'port': x.rsplit(':', 1)[1],
                'db': 0
            },
            self.endpoint
        ))
        self.redis = aioredis_cluster.create_redis_cluster(
            list(map(
                lambda x: (x.rsplit(':', 1)[0], int(x.rsplit(':', 1)[1])),
                self.endpoint
            )),
            cluster_commands_factory=cluster_commands_factory,
            retry_min_delay=retry_min_delay,
            retry_max_delay=retry_max_delay,
            max_attempts=max_attempts,
            attempt_timeout=attempt_timeout,
            state_reload_interval=state_reload_interval,
            follow_cluster=follow_cluster,
            idle_connection_timeout=idle_connection_timeout,
            username=username,
            password=password,
            encoding=encoding,
            pool_minsize=pool_minsize,
            pool_maxsize=pool_maxsize,
            connect_timeout=connect_timeout,
            ssl=ssl,
        )


class SyncRedisCluster:

    @classmethod
    @lru_cache
    def _get_connections(cls, endpoint: list):
        return list(map(
            lambda x: {
                'host': x.rsplit(':', 1)[0],
                'port': x.rsplit(':', 1)[1]
            },
            endpoint
        ))

    def __init__(self, endpoint=settings.redis_endpoint):
        self.endpoint = endpoint
        self.connections = self._get_connections(self.endpoint)
        self.redis = rediscluster.RedisCluster(
            startup_nodes=self.connections,
            max_connections=None,
            max_connections_per_node=False,
            init_slot_cache=True,
            readonly_mode=False,
            reinitialize_steps=None,
            skip_full_coverage_check=False,
            nodemanager_follow_cluster=False,
            connection_class=None,
            read_from_replicas=False,
            cluster_down_retry_attempts=3,
            host_port_remap=None,
            decode_responses=True
        )
