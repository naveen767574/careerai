"""
scripts/seed_golden_set.py

Load the human-labeled golden set (data/golden_set.seed.json) into the
`eval_cases` table. Idempotent: upserts by (title, company) so re-running keeps
the set in sync with the seed file instead of duplicating rows.

Usage (from backend/):
    python -m scripts.seed_golden_set

The seed JSON is the source of truth (version-controlled, diffable). This script
just mirrors it into the DB so offline_eval.py can read it.
"""
import json
import sys
from pathlib import Path

from app.database import SessionLocal
from app.models.eval_case import EvalCase

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "golden_set.seed.json"


def _normalize_skill(s: str) -> str:
    return (s or "").strip().lower()


def seed() -> int:
    if not SEED_PATH.exists():
        print(f"[seed_golden_set] seed file not found: {SEED_PATH}", file=sys.stderr)
        return 0

    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    cases = data.get("cases", [])

    session = SessionLocal()
    upserted = 0
    try:
        for c in cases:
            title = (c.get("title") or "").strip()
            company = (c.get("company") or "").strip() or None
            if not title:
                continue

            expected = sorted({_normalize_skill(s) for s in c.get("expected_skills", []) if s})

            existing = (
                session.query(EvalCase)
                .filter(EvalCase.title == title, EvalCase.company == company)
                .first()
            )
            if existing:
                existing.description = c.get("description", "") or ""
                existing.expected_skills = expected
                existing.expected_role_type = c.get("expected_role_type")
                existing.notes = c.get("notes")
            else:
                session.add(
                    EvalCase(
                        title=title,
                        company=company,
                        description=c.get("description", "") or "",
                        expected_skills=expected,
                        expected_role_type=c.get("expected_role_type"),
                        notes=c.get("notes"),
                    )
                )
            upserted += 1

        session.commit()
    finally:
        session.close()

    print(f"[seed_golden_set] upserted {upserted} eval case(s) from {SEED_PATH.name}")
    return upserted


if __name__ == "__main__":
    seed()
