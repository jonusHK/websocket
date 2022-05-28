from functools import lru_cache

from server import config


@lru_cache()
def get_settings():
    return config.Settings()


settings = get_settings()
DATABASE_URL = 'mysql+pymysql://{username}:{password}@{host}:{port}/{db_name}'.format(
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port,
    db_name=settings.db_name
)
