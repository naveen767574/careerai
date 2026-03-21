"""create auth tables

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2024-01-01
"""

revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

#revision = "001"
#down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("token", sa.String(length=512), nullable=False, unique=True, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_url", sa.String(length=2048), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "resume_data",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("email", sa.String(length=255)),
        sa.Column("phone", sa.String(length=50)),
        sa.Column("linkedin", sa.String(length=255)),
        sa.Column("github", sa.String(length=255)),
        sa.Column("portfolio", sa.String(length=255)),
        sa.Column("summary", sa.Text),
    )

    op.create_table(
        "resume_analyses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), index=True),
        sa.Column("ats_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("extracted_skills", sa.JSON),
        sa.Column("missing_sections", sa.JSON),
        sa.Column("analysis_json", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("skill_name", sa.String(length=100)),
        sa.Column("category", sa.String(length=100)),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("name", sa.String(length=255)),
        sa.Column("description", sa.Text),
        sa.Column("technologies", sa.String(length=255)),
    )

    op.create_table(
        "educations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("institution", sa.String(length=255)),
        sa.Column("degree", sa.String(length=255)),
        sa.Column("field", sa.String(length=255)),
        sa.Column("start_year", sa.Integer),
        sa.Column("end_year", sa.Integer),
    )

    op.create_table(
        "experiences",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("company", sa.String(length=255)),
        sa.Column("role", sa.String(length=255)),
        sa.Column("description", sa.Text),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
    )

    op.create_table(
        "internships",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("application_url", sa.String(length=500), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("posted_date", sa.Date, nullable=True),
        sa.Column("salary_range", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("duplicate_hash", sa.String(length=64), unique=True, nullable=True),
    )
    op.create_index("idx_internships_company", "internships", ["company"])
    op.create_index("idx_internships_location", "internships", ["location"])
    op.create_index("idx_internships_active", "internships", ["is_active"])
    op.create_index("idx_internships_source", "internships", ["source"])

    op.create_table(
        "internship_skills",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("internship_id", sa.Integer, sa.ForeignKey("internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_internship_skills_internship_id", "internship_skills", ["internship_id"])
    op.create_index("idx_internship_skills_name", "internship_skills", ["skill_name"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("internship_id", sa.Integer, sa.ForeignKey("internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("similarity_score", sa.Float, nullable=False),
        sa.Column("match_percentage", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "internship_id", name="uq_recommendations_user_internship"),
    )
    op.create_index("idx_recommendations_user_id", "recommendations", ["user_id"])
    op.create_index("idx_recommendations_score", "recommendations", ["similarity_score"])


def downgrade():
    op.drop_table("recommendations")
    op.drop_table("internship_skills")
    op.drop_table("internships")
    op.drop_table("experiences")
    op.drop_table("educations")
    op.drop_table("projects")
    op.drop_table("skills")
    op.drop_table("resume_analyses")
    op.drop_table("resume_data")
    op.drop_table("resumes")
    op.drop_table("password_reset_tokens")
    op.drop_table("users")

