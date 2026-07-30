"""
app/models/interaction_event.py

Append-only event log (Phase 0 — Instrumentation).

Every meaningful user interaction with the matching system is recorded here so
that later phases can be validated with *data* instead of opinion:
  • exposure   → `recommendations_served` (what we showed, in what order)
  • engagement → `match_viewed`, `whatif_simulated`
  • outcome    → `application_status_changed` (the training signal for Phase 5)

Design contract:
  • APPEND-ONLY. The app never UPDATEs or DELETEs rows here.
  • Nullable FKs with ON DELETE SET NULL — deleting a user/internship must never
    be blocked by, and never destroys, historical events (kept for analytics).
  • `payload` is JSON so new event fields can be added without a migration.
  • Writes are best-effort (see services/event_logger.py) and must never break a
    request; this model just defines the shape.

This table is high-volume by design → BigInteger primary key.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InteractionEvent(Base):
    __tablename__ = "interaction_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Nullable + SET NULL: keep the event even if the user is later deleted.
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Context internship (when the event is about one). Nullable + SET NULL.
    internship_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("internships.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # Event-specific data, e.g.:
    #   recommendations_served     → {"shown": [{"internship_id": 12, "match_pct": 78.0, "rank": 1}, ...]}
    #   match_viewed               → {"match_pct": 78.0, "matched": 3, "missing": 4}
    #   whatif_simulated           → {"skill": "sql", "delta_pct": 12.5}
    #   application_status_changed → {"from_status": "saved", "to_status": "applied"}
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    user = relationship("User")
    internship = relationship("Internship")

    __table_args__ = (
        Index("idx_interaction_events_type", "event_type"),
        Index("idx_interaction_events_user", "user_id"),
        Index("idx_interaction_events_created", "created_at"),
        # Rollups filter by type over a time window (e.g. apply-rate this week).
        Index("idx_interaction_events_type_created", "event_type", "created_at"),
    )
