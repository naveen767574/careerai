"""create instrumentation tables (Phase 0)

Adds two additive, non-invasive tables:

  • interaction_events — append-only event log (exposure / engagement / outcome).
    Feeds offline metrics now and the Phase 5 learned ranker later.
  • eval_cases — human-labeled golden set for offline evaluation of skill
    extraction / scoring / explanations.

No existing table is altered. FKs are nullable with ON DELETE SET NULL so this
table never blocks deleting a user or internship. Statements are IF NOT EXISTS
so the migration is safe alongside Base.metadata.create_all() at app startup.

Revision ID: a1b2c3d4e5f0
Revises: d4e5f6a1b2ca
Create Date: 2026-07-19
"""

revision = 'a1b2c3d4e5f0'
down_revision = 'd4e5f6a1b2ca'
branch_labels = None
depends_on = None

from alembic import op


def upgrade():
    # ── interaction_events ────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS interaction_events (
            id             BIGSERIAL PRIMARY KEY,
            user_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,
            event_type     VARCHAR(50) NOT NULL,
            internship_id  INTEGER REFERENCES internships(id) ON DELETE SET NULL,
            payload        JSON,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_interaction_events_type ON interaction_events (event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_interaction_events_user ON interaction_events (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_interaction_events_created ON interaction_events (created_at)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_interaction_events_type_created "
        "ON interaction_events (event_type, created_at)"
    )

    # ── eval_cases ────────────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS eval_cases (
            id                 SERIAL PRIMARY KEY,
            internship_id      INTEGER REFERENCES internships(id) ON DELETE SET NULL,
            title              VARCHAR(255) NOT NULL,
            company            VARCHAR(255),
            description        TEXT NOT NULL,
            expected_skills    JSON NOT NULL DEFAULT '[]',
            expected_role_type VARCHAR(50),
            notes              TEXT,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_eval_cases_internship ON eval_cases (internship_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_eval_cases_role ON eval_cases (expected_role_type)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS interaction_events")
    op.execute("DROP TABLE IF EXISTS eval_cases")
