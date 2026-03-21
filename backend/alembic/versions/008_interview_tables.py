"""create interview agent tables

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2024-01-01
"""

revision = 'b2c3d4e5f6a8'
down_revision = 'a1b2c3d4e5f7'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(100), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("internship_id", sa.Integer(), sa.ForeignKey("internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("readiness_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_interview_sessions_user_id", "interview_sessions", ["user_id"])

    op.create_table(
        "interview_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(100), sa.ForeignKey("interview_sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("difficulty", sa.String(10), nullable=True),
        sa.Column("skill_tested", sa.String(100), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_interview_questions_session", "interview_questions", ["session_id"])

    op.create_table(
        "interview_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("verdict", sa.String(20), nullable=True),
        sa.Column("strengths", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("weaknesses", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("model_answer", sa.Text(), nullable=True),
        sa.Column("improvement_tip", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_interview_answers_session", "interview_answers", ["session_id"])
    op.create_index("idx_interview_answers_user_id", "interview_answers", ["user_id"])

    op.create_table(
        "interview_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(100), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("internship_id", sa.Integer(), sa.ForeignKey("internships.id"), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("technical_score", sa.Float(), nullable=False),
        sa.Column("behavioral_score", sa.Float(), nullable=False),
        sa.Column("readiness_level", sa.String(20), nullable=False),
        sa.Column("top_strengths", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("top_improvements", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("recommended_resources", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_interview_reports_user_id", "interview_reports", ["user_id"])


def downgrade():
    op.drop_table("interview_reports")
    op.drop_table("interview_answers")
    op.drop_table("interview_questions")
    op.drop_table("interview_sessions")

