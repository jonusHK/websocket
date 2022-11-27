"""add uploaded_by column for S3Media

Revision ID: ecd7931810ea
Revises: 349801289749
Create Date: 2022-11-27 16:36:22.988754

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ecd7931810ea'
down_revision = '349801289749'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('s3_media', sa.Column('uploaded_by_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(None, 's3_media', 'users', ['uploaded_by_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 's3_media', type_='foreignkey')
    op.drop_column('s3_media', 'uploaded_by_id')
    # ### end Alembic commands ###