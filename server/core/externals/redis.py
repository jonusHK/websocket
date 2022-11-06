import aioredis

from server.db.databases import settings


class AioRedis:
    def __init__(
            self,
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_database,
            decode_responses=True
    ):
        self.host = host
        self.port = port
        self.db = db
        self.decode_responses = decode_responses
        self.redis = aioredis.from_url(
            "redis://%s:%s" % (self.host, self.port),
            db=self.db,
            decode_responses=self.decode_responses)

    def __enter__(self):
        return self.redis

    def __exit__(self):
        await self.redis.close()
