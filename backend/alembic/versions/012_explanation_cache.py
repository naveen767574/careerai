"""create explanation_cache table (Phase 3)

Additive, non-invasive. Caches grounded match explanations keyed by
(user_id, job_id, resume_version).

Keys are TEXT rather than FK integers deliberately: the cache is a DERIVED
artifact, not relational truth. It must never block deleting a user or an
internship, and resume_version can be a synthetic marker ("v0") for users who
have not uploaded a resume yet.

Statements are IF NOT EXISTS so this migration is safe alongside
Base.metadata.create_all() at app startup.

Revision ID: e5f6a1b2c3d1
Revises: a1b2c3d4e5f0
Create Date: 2026-07-30
"""

revision = 'e5f6a1b2c3d1'
down_revision = 'a1b2c3d4e5f0'
branch_labels = None
depends_on = None

from alembic import op


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS explanation_cache (
            user_id          VARCHAR(64) NOT NULL,
            job_id           VARCHAR(64) NOT NULL,
            resume_version   VARCHAR(64) NOT NULL,
            explanation_json JSON        NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, job_id, resume_version)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_explanation_cache_user "
        "ON explanation_cache (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_explanation_cache_created "
        "ON explanation_cache (created_at)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_explanation_cache_created")
    op.execute("DROP INDEX IF EXISTS idx_explanation_cache_user")
    op.execute("DROP TABLE IF EXISTS explanation_cache")
