from datetime import datetime

from pydantic import BaseModel


class S3MediaBaseS(BaseModel):
    bucket_name: str
    filename: str
    filepath: str
    content_type: str


class S3MediaCreateS(S3MediaBaseS):
    pass


class S3MediaS(S3MediaBaseS):
    id: int
    use_type: str
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True
