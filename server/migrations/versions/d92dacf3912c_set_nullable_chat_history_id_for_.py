"""set nullable chat_history_id for ChatHistoryFile

Revision ID: d92dacf3912c
Revises: 7eb83477a0e3
Create Date: 2022-11-30 23:12:24.787072

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'd92dacf3912c'
down_revision = '7eb83477a0e3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('chat_history_files', 'chat_history_id',
               existing_type=mysql.BIGINT(),
               nullable=True)
    op.drop_constraint('chat_history_files_ibfk_1', 'chat_history_files', type_='foreignkey')
    op.create_foreign_key(None, 'chat_history_files', 'chat_histories', ['chat_history_id'], ['id'])
    op.alter_column('s3_media', 'filepath',
               existing_type=mysql.VARCHAR(length=200),
               nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('s3_media', 'filepath',
               existing_type=mysql.VARCHAR(length=200),
               nullable=True)
    op.drop_constraint(None, 'chat_history_files', type_='foreignkey')
    op.create_foreign_key('chat_history_files_ibfk_1', 'chat_history_files', 'chat_histories', ['chat_history_id'], ['id'], ondelete='CASCADE')
    op.alter_column('chat_history_files', 'chat_history_id',
               existing_type=mysql.BIGINT(),
               nullable=False)
    # ### end Alembic commands ###
