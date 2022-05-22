"""fix user_profile_images model

Revision ID: 3a6b3d26efe8
Revises: 71f8144b2697
Create Date: 2022-05-22 18:34:40.254170

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '3a6b3d26efe8'
down_revision = '71f8144b2697'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('s3_media', sa.Column('type', sa.String(length=50), nullable=True))
    op.drop_column('s3_media', 'inherit_type')
    op.drop_index('ix_user_profile_images_id', table_name='user_profile_images')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index('ix_user_profile_images_id', 'user_profile_images', ['id'], unique=False)
    op.add_column('s3_media', sa.Column('inherit_type', mysql.VARCHAR(length=50), nullable=True))
    op.drop_column('s3_media', 'type')
    # ### end Alembic commands ###
