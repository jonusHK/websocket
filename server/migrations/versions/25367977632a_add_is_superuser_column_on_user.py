"""add is_superuser column on User

Revision ID: 25367977632a
Revises: 5b279f15806a
Create Date: 2022-08-27 02:48:30.361910

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '25367977632a'
down_revision = '5b279f15806a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('is_superuser', sa.Boolean(), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'is_superuser')
    # ### end Alembic commands ###
