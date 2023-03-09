import ssl
import time
from copy import deepcopy
from typing import Optional, List

import aioredis
import aioredis_cluster
from aioredis_cluster.typedef import CommandsFactory
from rediscluster import RedisCluster as SyncRedisCluster

from server.db.databases import settings


class AioRedis:

    RETRY_COUNT = 5
    RETRY_DELAY = 0.2

    def _get_connections(self):
        connections = []
        for _ in range(self.RETRY_COUNT):
            for ep in self.endpoint:
                try:
                    conn = aioredis.Redis.from_url(
                        ep,
                        db=self.db,
                        encoding=self.encoding,
                        max_connections=self.max_connections,
                        decode_responses=self.decode_responses
                    )
                except:
                    time.sleep(self.RETRY_DELAY)
                else:
                    connections.append(conn)
            if connections:
                return connections
        raise ConnectionError('Failed to connect Redis.')

    def __init__(
        self,
        endpoint: List[str] = settings.redis_endpoint,
        db: int = settings.redis_database,
        encoding: str = "utf-8",
        max_connections: int = 10,
        decode_responses: bool = True,
    ):
        self.endpoint = endpoint
        self.db = db
        self.encoding = encoding
        self.max_connections = max_connections
        self.decode_responses = decode_responses
        self.connections = self._get_connections()
