"""lengthen the filepath for S3Media

Revision ID: 7eb83477a0e3
Revises: ecd7931810ea
Create Date: 2022-11-27 22:40:31.436642

"""
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '7eb83477a0e3'
down_revision = 'ecd7931810ea'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('s3_media', 'filepath',
                    existing_type=mysql.VARCHAR(length=100),
                    type_=mysql.VARCHAR(length=200))


def downgrade():
    op.alter_column('s3_media', 'filepath',
                    existing_type=mysql.VARCHAR(length=200),
                    type_=mysql.VARCHAR(length=100))
