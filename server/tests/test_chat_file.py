import base64
import os
import mimetypes

from server.core.enums import ChatType
from server.models import S3Media
from server.schemas.chat import ChatReceiveFormS, ChatReceiveDataS, ChatReceiveFileS


async def test_list_buckets(db_setup, db_session, s3_client, s3_bucket):
    my_client = S3Media.get_s3_client()

    f = open('./static/images/potato.png', 'rb')
    filename = os.path.basename(f.name)
    content_type, _ = mimetypes.guess_type(filename)

    receive = ChatReceiveFormS(
        type=ChatType.FILE.name.lower(),
        data=ChatReceiveDataS(
            files=[
                ChatReceiveFileS(
                    content=base64.b64encode(f.read()),
                    content_type=content_type,
                    filename=filename,
                )
            ]
        ))

    f.close()


