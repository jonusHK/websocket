"""add user profile image

Revision ID: 1b09278a4268
Revises: f89ad05e8d41
Create Date: 2022-05-08 19:05:46.972687

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from server.core import utils
from server.core.enums import ProfileImageType

revision = '1b09278a4268'
down_revision = 'f89ad05e8d41'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_profile_images',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('user_profile_id', sa.BigInteger(), nullable=False),
    sa.Column('type', utils.IntTypeEnum(enum_class=ProfileImageType), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_profile_id'], ['user_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_profile_images_id'), 'user_profile_images', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_user_profile_images_id'), table_name='user_profile_images')
    op.drop_table('user_profile_images')
    # ### end Alembic commands ###
