from server.crud import CRUDBase
from server.models import S3Media


class S3MediaCRUD(CRUDBase):
    model = S3Media
