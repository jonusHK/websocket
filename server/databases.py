from functools import lru_cache

from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

from server import config


@lru_cache()
def get_settings():
    return config.Settings()


settings = get_settings()
DATABASE_URL = "mysql+pymysql://{username}:{password}@{host}:{port}/{db_name}".format(
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port,
    db_name=settings.db_name
)

# sessionmaker : 엔진의 연결 풀을 요청하고, 새로운 세션 객체와 연결하여, 새로운 세션 객체를 초기화하는 자동화 기능을 수행함.
# scoped_session : 생성된 세션 객체들의 레지스트리(registry). 여기서 레지스트리의 Key는 특정한 형태의 thread-safe id.
DBSession = scoped_session(sessionmaker())
Base = declarative_base()


def initialize_sql(engine):
    DBSession.configure(autocommit=False, autoflush=True, bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
