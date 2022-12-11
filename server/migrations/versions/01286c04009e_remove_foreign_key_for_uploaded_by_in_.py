"""remove foreign key for uploaded_by in S3Media

Revision ID: 01286c04009e
Revises: 78af8f3022b3
Create Date: 2022-12-04 16:48:01.763603

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '01286c04009e'
down_revision = '78af8f3022b3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('s3_media_ibfk_2', 's3_media', type_='foreignkey')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_foreign_key('s3_media_ibfk_2', 's3_media', 'user_profiles', ['uploaded_by_id'], ['id'])
    # ### end Alembic commands ###