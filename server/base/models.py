from sqlalchemy import BigInteger, Column, String, DateTime, func

from server.databases import Base


class TimestampMixin(object):
    created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)


class S3Media(TimestampMixin, Base):
    __tablename__ = "s3_media"

    id = Column(BigInteger, primary_key=True, index=True)
    bucket_name = Column(String(50), nullable=False)
    file_key = Column(String(45), nullable=False)
    file_path = Column(String(100), nullable=False)
    content_type = Column(String(45), nullable=False)
    type = Column(String(50), nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 's3_media',
        'polymorphic_on': type,
        'with_polymorphic': '*'
    }
