"""
app/models/eval_case.py

Golden-set ground truth (Phase 0 — Instrumentation).

A small, HUMAN-labeled set of internships used to measure the quality of the
skill-extraction / scoring / explanation paths offline. This is the reference
the whole roadmap is graded against:
  • Phase 2 (LLM skill extraction) ships only if it beats the recorded baseline
    on `expected_skills` precision/recall.
  • Phase 3 (grounded explanations) reuses these cases to assert explanations
    reference only real matched skills.

Design notes:
  • Rows are CURATED and version-controlled via data/golden_set.seed.json — the
    seed script upserts them so the set is reproducible and diffable.
  • title / company / description are DENORMALIZED (copied in, not just FK'd) so a
    case survives even if the source internship row is deleted or re-scraped.
  • `expected_skills` is the ground truth — labeled by a human, never by an LLM
    (auto-labeling would defeat the purpose of an independent yardstick).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Link to a real internship when one exists; SET NULL so deleting/ re-scraping
    # the internship never destroys the labeled case (we keep the denormalized text).
    internship_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("internships.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Ground truth — the correct required skills for this posting (lowercased).
    expected_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Optional labeled role, e.g. "data" | "backend" | "frontend".
    expected_role_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    internship = relationship("Internship")

    __table_args__ = (
        Index("idx_eval_cases_internship", "internship_id"),
        Index("idx_eval_cases_role", "expected_role_type"),
    )
