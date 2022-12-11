"""add room type for ChatRoom

Revision ID: e68bbe70d208
Revises: 5994ccc6cdf2
Create Date: 2022-12-11 18:13:33.966143

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
import server
from server.core.enums import ChatRoomType

revision = 'e68bbe70d208'
down_revision = '5994ccc6cdf2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('chat_room_user_association', 'type')
    op.add_column('chat_rooms', sa.Column('type', server.core.utils.IntTypeEnum(enum_class=ChatRoomType), nullable=False))
    op.alter_column('chat_rooms', 'name',
               existing_type=mysql.VARCHAR(length=30),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('chat_rooms', 'name',
               existing_type=mysql.VARCHAR(length=30),
               nullable=False)
    op.drop_column('chat_rooms', 'type')
    op.add_column('chat_room_user_association', sa.Column('type', mysql.INTEGER(), autoincrement=False, nullable=False))
    # ### end Alembic commands ###
