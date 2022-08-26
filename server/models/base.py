from datetime import datetime

import sqlalchemy as sa
from pydantic import BaseModel
from sqlmodel import SQLModel as _SQLModel, Field


class SQLModel(_SQLModel):
    class Config:
        arbitrary_types_allowed = True


class TimestampMixin(BaseModel):
    created: datetime = Field(
        sa_column=sa.Column(sa.DateTime(timezone=True), default=sa.func.now()))
    modified: datetime = Field(
        sa_column=sa.Column(sa.DateTime(timezone=True), default=sa.func.now(), onupdate=sa.func.now()))


class S3Media(SQLModel, TimestampMixin, table=True):
    __tablename__ = "s3_media"

    id: int = Field(primary_key=True, index=True)
    bucket_name: str = Field(max_length=50)
    file_key: str = Field(max_length=45)
    file_path: str = Field(max_length=100)
    content_type: str = Field(max_length=45)
    use_type: str = Field(max_length=50)

    __mapper_args__ = {
        "polymorphic_identity": "s3_media",
        "polymorphic_on": "use_type",
        "with_polymorphic": "*"
    }

    class Config:
        arbitrary_types_allowed = True
