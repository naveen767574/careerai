"""
app/models/explanation_cache.py

Phase 3 — cache for grounded match explanations.

WHY a cache: explanations are expensive (one LLM call) but almost perfectly
stable — for a given (user, job, resume_version) the inputs (matched_skills,
missing_skills, score) are already deterministic, so the output should be too.
Caching turns a per-view LLM call into a once-per-resume-version call.

Cache key = (user_id, job_id, resume_version):
  • user_id + job_id  → identifies the pair being explained
  • resume_version    → the ONLY thing that legitimately invalidates an
                        explanation. When the user edits their resume their
                        skills change, so matched/missing change, so the
                        explanation must be regenerated.

Keys are TEXT (not FK integers) on purpose: the cache is a derived artifact,
not relational truth. It must never block a user/internship delete, and
resume_version may be a synthetic marker ("v0") for users with no resume yet.
"""
from datetime import datetime

from sqlalchemy import DateTime, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExplanationCache(Base):
    __tablename__ = "explanation_cache"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    resume_version: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Serialized ExplanationOutput — already validated/grounded before write.
    explanation_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_explanation_cache_user", "user_id"),
        Index("idx_explanation_cache_created", "created_at"),
    )
