"""remove  for ChatHistory.

Revision ID: 1cba91274e95
Revises: db38e0bcf7ae
Create Date: 2022-11-06 21:59:39.296638

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '1cba91274e95'
down_revision = 'db38e0bcf7ae'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('chat_histories', 'is_read')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('chat_histories', sa.Column('is_read', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False))
    # ### end Alembic commands ###
