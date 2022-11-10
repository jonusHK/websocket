import aioredis

from server.db.databases import settings


class AioRedis:
    def __init__(
            self,
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_database,
            encoding="utf-8",
            max_connections=10,
            decode_responses=True
    ):
        self.host = host
        self.port = port
        self.db = db
        self.encoding = encoding
        self.max_connections = max_connections
        self.decode_responses = decode_responses
        self.redis = aioredis.Redis.from_url(
            "redis://%s:%s" % (self.host, self.port),
            db=self.db,
            encoding=self.encoding,
            max_connections=self.max_connections,
            decode_responses=self.decode_responses)
