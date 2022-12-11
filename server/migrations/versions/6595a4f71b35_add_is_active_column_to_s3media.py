"""add is_active column to S3Media

Revision ID: 6595a4f71b35
Revises: d3ba8587e1fd
Create Date: 2022-12-04 19:55:58.112621

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '6595a4f71b35'
down_revision = 'd3ba8587e1fd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('chat_histories', 'is_active')
    op.add_column('s3_media', sa.Column('is_active', sa.Boolean(), nullable=False))
    op.drop_column('user_profiles', 'is_active')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user_profiles', sa.Column('is_active', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False))
    op.drop_column('s3_media', 'is_active')
    op.add_column('chat_histories', sa.Column('is_active', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False))
    # ### end Alembic commands ###