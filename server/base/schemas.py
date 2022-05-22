from pydantic import BaseModel


class S3MediaBase(BaseModel):
    bucket_name: str
    file_key: str
    file_path: str
    content_type: str


class S3MediaCreate(S3MediaBase):
    pass


class S3Media(S3MediaBase):
    id: int
    type: str
