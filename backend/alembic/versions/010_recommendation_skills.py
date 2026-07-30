"""add matched_skills / missing_skills to recommendations

Persists the semantic (cosine >= 0.70) matched/missing skill lists computed at
refresh time, so read paths never recompute embeddings and stay consistent with
the match score.

Revision ID: d4e5f6a1b2ca
Revises: c3d4e5f6a1b9
Create Date: 2026-07-09
"""

revision = 'd4e5f6a1b2ca'
down_revision = 'c3d4e5f6a1b9'
branch_labels = None
depends_on = None

from alembic import op


def upgrade():
    # Idempotent ADD COLUMN IF NOT EXISTS — safe whether the table was created by
    # Alembic or by SQLAlchemy's Base.metadata.create_all(). JSON stores a list of
    # skill strings; nullable so pre-existing rows remain valid until next refresh.
    op.execute("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS matched_skills JSON")
    op.execute("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS missing_skills JSON")


def downgrade():
    op.execute("ALTER TABLE recommendations DROP COLUMN IF EXISTS matched_skills")
    op.execute("ALTER TABLE recommendations DROP COLUMN IF EXISTS missing_skills")
