"""create notifications and chat_logs tables

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2024-01-01
"""

revision = 'e5f6a1b2c3d4'
down_revision = 'd4e5f6a1b2c3'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

#revision = "005"
#down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_notifications_user_id", "notifications", ["user_id"])
    op.create_index("idx_notifications_is_read", "notifications", ["user_id", "is_read"])
    op.create_index("idx_notifications_expires", "notifications", ["expires_at"])

    op.create_table(
        "chat_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_chat_logs_user_session", "chat_logs", ["user_id", "session_id"])
    op.create_index("idx_chat_logs_created_at", "chat_logs", ["created_at"])


def downgrade():
    op.drop_index("idx_chat_logs_created_at", table_name="chat_logs")
    op.drop_index("idx_chat_logs_user_session", table_name="chat_logs")
    op.drop_table("chat_logs")
    op.drop_index("idx_notifications_expires", table_name="notifications")
    op.drop_index("idx_notifications_is_read", table_name="notifications")
    op.drop_index("idx_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

