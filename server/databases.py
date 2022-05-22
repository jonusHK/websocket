from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

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

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
