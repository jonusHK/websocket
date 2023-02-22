import aioredis

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
        self.endpoint = endpoint
        self.db = db
        self.encoding = encoding
        self.max_connections = max_connections
        self.decode_responses = decode_responses
        self.redis = aioredis.Redis.from_url(
            'redis://%s' % (
                self.endpoint[0] if len(self.endpoint) == 1
                else ','.join(self.endpoint)
            ),
            db=self.db,
            encoding=self.encoding,
            max_connections=self.max_connections,
            decode_responses=self.decode_responses
        )
