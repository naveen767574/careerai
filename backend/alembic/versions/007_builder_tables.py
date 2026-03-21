"""create builder agent tables

Revision ID: a1b2c3d4e5f7
Revises: f6a1b2c3d4e5
Create Date: 2024-01-01
"""

revision = 'a1b2c3d4e5f7'
down_revision = 'f6a1b2c3d4e5'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "builder_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(100), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("resume_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("selected_template", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_builder_sessions_user_id", "builder_sessions", ["user_id"])

    op.create_table(
        "resume_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("resume_data", sa.JSON(), nullable=False),
        sa.Column("template_name", sa.String(100), nullable=True),
        sa.Column("ats_score", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="builder"),
        sa.Column("pdf_path", sa.String(500), nullable=True),
        sa.Column("docx_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "version_number", name="uq_user_version"),
    )
    op.create_index("idx_resume_versions_user_id", "resume_versions", ["user_id"])


def downgrade():
    op.drop_table("resume_versions")
    op.drop_table("builder_sessions")

