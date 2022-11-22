from pydantic import BaseModel


class S3MediaBaseS(BaseModel):
    bucket_name: str
    file_key: str
    file_path: str
    content_type: str


class S3MediaCreateS(S3MediaBaseS):
    pass


class S3MediaS(S3MediaBaseS):
    id: int
    use_type: str

    class Config:
        orm_mode = True
