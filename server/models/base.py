from sqlalchemy import BigInteger, Column, String, DateTime, func

from server.models import Base


class TimestampMixin(object):
    created = Column(DateTime(timezone=True), default=func.now())
    updated = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())


class S3Media(TimestampMixin, Base):
    __tablename__ = "s3_media"

    id = Column(BigInteger, primary_key=True, index=True)
    bucket_name = Column(String(50), nullable=False)
    file_key = Column(String(45), nullable=False)
    file_path = Column(String(100), nullable=False)
    content_type = Column(String(45), nullable=False)
    use_type = Column(String(50), nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 's3_media',
        'polymorphic_on': use_type,
        'with_polymorphic': '*'
    }
