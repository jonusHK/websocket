"""modify name of columns for S3Media

Revision ID: 494ba59742ef
Revises: d79ff50606ce
Create Date: 2022-11-27 15:00:00.253611

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '494ba59742ef'
down_revision = 'd79ff50606ce'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('s3_media', sa.Column('filename', sa.String(length=45), nullable=False))
    op.add_column('s3_media', sa.Column('filepath', sa.String(length=100), nullable=False))
    op.drop_column('s3_media', 'file_path')
    op.drop_column('s3_media', 'file_key')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('s3_media', sa.Column('file_key', mysql.VARCHAR(length=45), nullable=False))
    op.add_column('s3_media', sa.Column('file_path', mysql.VARCHAR(length=100), nullable=False))
    op.drop_column('s3_media', 'filepath')
    op.drop_column('s3_media', 'filename')
    # ### end Alembic commands ###
