from datetime import datetime
from io import BytesIO

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


class WebSocketFileS(BaseModel):
    content: BytesIO
    content_type: str
    filename: str

    class Config:
        arbitrary_types_allowed = True
