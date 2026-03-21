"""create linkedin agent tables

Revision ID: c3d4e5f6a1b9
Revises: b2c3d4e5f6a8
Create Date: 2024-01-01
"""

revision = 'c3d4e5f6a1b9'
down_revision = 'b2c3d4e5f6a8'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "linkedin_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(100), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_input", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_linkedin_sessions_user_id", "linkedin_sessions", ["user_id"])

    op.create_table(
        "linkedin_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(100), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_score", sa.Integer(), nullable=False),
        sa.Column("score_breakdown", sa.JSON(), nullable=False),
        sa.Column("gap_analysis", sa.JSON(), nullable=False),
        sa.Column("headline_variants", sa.JSON(), nullable=False),
        sa.Column("about_section", sa.Text(), nullable=True),
        sa.Column("experience_improvements", sa.JSON(), nullable=True),
        sa.Column("skills_optimization", sa.JSON(), nullable=True),
        sa.Column("improvement_priority", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id"], ["linkedin_sessions.session_id"]),
    )
    op.create_index("idx_linkedin_reports_user_id", "linkedin_reports", ["user_id"])


def downgrade():
    op.drop_table("linkedin_reports")
    op.drop_table("linkedin_sessions")

