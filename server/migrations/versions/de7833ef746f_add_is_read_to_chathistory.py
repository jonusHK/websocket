"""add `is_read` to ChatHistory`

Revision ID: de7833ef746f
Revises: 9bd0ecff721f
Create Date: 2022-11-04 16:31:26.662851

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'de7833ef746f'
down_revision = '9bd0ecff721f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('chat_histories', sa.Column('is_read', sa.Boolean(), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('chat_histories', 'is_read')
    # ### end Alembic commands ###
