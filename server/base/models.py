from sqlalchemy import BigInteger, Column, String

from server.databases import Base


class S3Media(Base):
    __tablename__ = "s3_media"

    id = Column(BigInteger, primary_key=True, index=True)
    bucket_name = Column(String(50), nullable=False)
    file_key = Column(String(45), nullable=False)
    file_path = Column(String(100), nullable=False)
    content_type = Column(String(45), nullable=False)
