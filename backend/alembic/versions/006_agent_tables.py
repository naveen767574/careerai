"""create agent system tables

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2024-01-01
"""

revision = 'f6a1b2c3d4e5'
down_revision = 'e5f6a1b2c3d4'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

#revision = "006"
#down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("state_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(50), nullable=False),
        sa.Column("trigger", sa.String(100), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("idx_agent_runs_agent_name", "agent_runs", ["agent_name"])
    op.create_index("idx_agent_runs_status", "agent_runs", ["status"])

    op.create_table(
        "skill_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("skill_name", sa.String(100), nullable=False),
        sa.Column("frequency_pct", sa.Float(), nullable=False),
        sa.Column("trend", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_skill_snapshots_user_id", "skill_snapshots", ["user_id"])
    op.create_index("idx_skill_snapshots_date", "skill_snapshots", ["snapshot_date"])

    op.create_table(
        "cover_letter_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("internship_id", sa.Integer(), sa.ForeignKey("internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_cover_letter_drafts_user_id", "cover_letter_drafts", ["user_id"])
    op.create_index("idx_cover_letter_drafts_status", "cover_letter_drafts", ["status"])


def downgrade():
    op.drop_table("cover_letter_drafts")
    op.drop_table("skill_snapshots")
    op.drop_table("agent_runs")
    op.drop_table("agent_state")

