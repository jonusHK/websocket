import asyncio
import functools
import os
import uuid
import warnings
from io import IOBase, BytesIO
from typing import List, Optional

import boto3
from PIL import Image
from botocore.exceptions import ClientError
from pdf2image import convert_from_bytes
from sqlalchemy import BigInteger, Column, String, DateTime, func, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, backref
from starlette.datastructures import UploadFile

from server.db.databases import Base, settings


class TimestampMixin(object):
    created = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class S3Media(TimestampMixin, Base):
    __tablename__ = "s3_media"

    _file: Optional[UploadFile] = None
    thumbnail_size = 300

    id = Column(BigInteger, primary_key=True, index=True)
    uid = Column(String(32), nullable=False, unique=True)
    origin_uid = Column(String(32), ForeignKey('s3_media.uid'), nullable=True)
    uploaded_by_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    bucket_name = Column(String(50), nullable=False)
    filename = Column(String(45), nullable=False)
    filepath = Column(String(250), nullable=False)
    content_type = Column(String(45), nullable=False)
    use_type = Column(String(50), nullable=True)

    origin = relationship('S3Media', remote_side=[uid], backref=backref('thumbnail', uselist=False))
    uploaded_by = relationship('User', back_populates='s3_medias', lazy='joined')

    __mapper_args__ = {
        'polymorphic_identity': 's3_media',
        'polymorphic_on': use_type,
        'with_polymorphic': '*'
    }

    def get_file(
        self,
        aws_access_key_id: str = settings.aws_access_key,
        aws_secret_access_key: str = settings.aws_secret_access_key
    ):
        if self._file is None:
            s3 = self.get_s3_client(aws_access_key_id, aws_secret_access_key)
            self._file = s3.download_file(self.bucket_name, self.filename, self.filepath)
        return self._file

    def file_exists(
        self,
        aws_access_key_id: str = settings.aws_access_key,
        aws_secret_access_key: str = settings.aws_secret_access_key
    ):
        s3 = self.get_s3_client(aws_access_key_id, aws_secret_access_key)
        try:
            s3.head_object(Bucket=self.bucket_name, Key=self.filepath)
        except ClientError:
            return False
        return True

    @classmethod
    @functools.cache
    def get_s3_client(
        cls,
        aws_access_key_id: str = settings.aws_access_key,
        aws_secret_access_key: str = settings.aws_secret_access_key
    ):
        return boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key)

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None

    @classmethod
    async def is_exists(
        cls, session: AsyncSession, filepath: str,
        bucket_name: str = settings.aws_storage_bucket_name, **kwargs
    ) -> bool:
        from server.crud.base import S3MediaCRUD
        from fastapi import HTTPException
        try:
            await S3MediaCRUD(session).get(conditions=(
                S3Media.filepath == filepath, S3Media.bucket_name == bucket_name))
        except HTTPException:
            return False
        return True

    @classmethod
    async def new(
        cls, session: AsyncSession, file: UploadFile, root: str = None,
        uploaded_by=None, upload=False, thumbnail=False, **kwargs
    ):
        uid = uuid.uuid4().hex

        root = 'media/' + root.lstrip('/') if root else ''
        if not root.endswith('/'):
            root += '/'

        if uploaded_by is not None:
            path_prefix = uploaded_by.id
        else:
            path_prefix = 'anonymous'

        root = os.path.join(root, f'{path_prefix}/{uid}/')

        filepath = f'{root}{file.filename}'
        if await cls.is_exists(session, filepath, **kwargs):
            raise FileExistsError(f'이미 파일이 존재합니다. {filepath}')

        instance = cls(
            uid=uid,
            filename=file.filename,
            filepath=filepath,
            content_type=file.content_type,
            uploaded_by=uploaded_by,
            **kwargs)
        instance._file = file
        if upload:
            await instance.upload()

        if thumbnail:
            if file.content_type.startswith('image/'):
                im_origin = Image.open(file.file)
                w, h = im_origin.size
                if max(w, h) <= cls.thumbnail_size:
                    return instance, None

                thumbnail = cls(
                    uid=uuid.uuid4().hex,
                    origin_uid=instance.uid,
                    filename=file.filename,
                    filepath=f'{root}thumbnail/{file.filename}',
                    content_type=file.content_type,
                    uploaded_by=uploaded_by,
                    **kwargs)
                im = im_origin

                try:
                    # exif 추출 및 rotation 정보 썸네일에 적용
                    if hasattr(im, '_getexif'):
                        _exif = im._getexif()
                        if _exif and 0x0112 in _exif:
                            _o = _exif.get(0x0112)
                            angle = {3: 180, 6: 270, 8: 90}.get(_o, 0)
                            if angle != 0:
                                im = im.rotate(angle, expand=True)
                except:
                    pass

                im.thumbnail((cls.thumbnail_size, cls.thumbnail_size), Image.ANTIALIAS)

                thumbnail._file = im
                if upload:
                    await thumbnail.upload()

                return instance, thumbnail

            elif file.content_type == 'application/pdf':
                for im in convert_from_bytes(await cls.file_to_io(instance)):
                    thumbnail = cls(
                        uid=uuid.uuid4().hex,
                        origin_uid=instance.uid,
                        filename=file.filename,
                        filepath=f'{root}thumbnail/{file.filename}',
                        content_type=file.content_type,
                        uploaded_by=uploaded_by,
                        **kwargs)
                    w, h = im.size
                    if max(w, h) > cls.thumbnail_size:
                        im.thumbnail((cls.thumbnail_size, cls.thumbnail_size), Image.ANTIALIAS)
                    thumbnail._file = im
                    if upload:
                        await thumbnail.upload()
                    return instance, thumbnail  # 첫 장만 썸네일로 저장
                else:
                    return instance, None

            else:
                warnings.warn(f'{instance.filename} is not a compressible type: {file.content_type}')

        return instance, None

    @classmethod
    async def file_to_io(
        cls, m: 'S3Media',
        aws_access_key_id: str = settings.aws_access_key,
        aws_secret_access_key: str = settings.aws_secret_access_key
    ) -> Optional[IOBase]:
        file = m.get_file(aws_access_key_id, aws_secret_access_key)

        if isinstance(file, IOBase):
            return file
        elif isinstance(file, UploadFile):
            await file.seek(0)
            io = BytesIO()
            while contents := await file.read(1024 * 1024):
                io.write(contents)
        elif isinstance(file, Image.Image):
            io = BytesIO()
            file.save(io, format=m.content_type.split('/')[-1].lower())
        else:
            warnings.warn(f'{file.filename}({m.id}) seems to be an invalid type: {type(file)}')
            return None
        return io

    @classmethod
    async def files_to_models(
        cls, session: AsyncSession, files: List[UploadFile], root: str = None,
        user=None, upload=False, thumbnail=False, **kwargs
    ):
        uploaded_by = None
        if user:
            uploaded_by = user

        for file in files:
            origin, thumb = await cls.new(
                session, file,
                root=root, uploaded_by=uploaded_by, upload=upload, thumbnail=thumbnail, **kwargs)
            yield origin
            if thumb is not None:
                yield thumb

    async def upload(
        self,
        file: UploadFile = None, overwrite=False,
        aws_access_key_id: str = settings.aws_access_key,
        aws_secret_access_key: str = settings.aws_secret_access_key
    ):
        s3 = self.get_s3_client(aws_access_key_id, aws_secret_access_key)

        if file:
            if self.file_exists(aws_access_key_id, aws_secret_access_key) and not overwrite:
                raise FileExistsError
            self._file = file

        b = await self.file_to_io(self, aws_access_key_id, aws_secret_access_key)
        if not b:
            raise IOError(f"File `{self.filepath}` doesn't seems to be type that uplodable.")

        b.seek(0)
        s3.upload_fileobj(**{
            'Fileobj': b,
            'Bucket': self.bucket_name,
            'Key': self.filepath,
            'ExtraArgs': {'ContentType': self.content_type},
        })
        b.close()

    @classmethod
    async def asynchronous_upload(
        cls,
        *media: 'S3Media',
        aws_access_key_id: str = settings.aws_access_key,
        aws_secret_access_key: str = settings.aws_secret_access_key
    ):
        s3 = cls.get_s3_client(aws_access_key_id, aws_secret_access_key)

        async def _upload(attr):
            return s3.upload_fileobj(**attr)

        io_list: List[IOBase] = []
        try:
            async def _upload_kwargs():
                for m in media:
                    b = await cls.file_to_io(m, aws_access_key_id, aws_secret_access_key)

                    if b is None:
                        continue

                    io_list.append(b)

                    b.seek(0)
                    yield {
                        'Fileobj': b,
                        'Bucket': m.bucket_name,
                        'Key': m.filepath,
                        'ExtraArgs': {'ContentType': m.content_type},
                    }
            await asyncio.wait([_upload(attr) async for attr in _upload_kwargs()])
        finally:
            for io in io_list:
                io.close()
