from functools import lru_cache

from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

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

DBSession = scoped_session(sessionmaker())
Base = declarative_base()


def initialize_sql(engine):
    DBSession.configure(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
