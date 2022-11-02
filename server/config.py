from functools import lru_cache
from typing import List

from pydantic import BaseSettings, AnyHttpUrl, validator


class Settings(BaseSettings):
    api_v1_prefix: str = "/api/v1"
    db_name: str
    db_username: str
    db_password: str
    db_host: str
    db_port: int
    backend_cors_origins: List[AnyHttpUrl] = []
    debug: bool
    session_secret_key: str

    @validator("backend_cors_origins", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
