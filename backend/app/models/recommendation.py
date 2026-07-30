from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    internship_id: Mapped[int] = mapped_column(
        ForeignKey("internships.id", ondelete="CASCADE"), index=True, nullable=False
    )
    similarity_score: Mapped[float] = mapped_column(nullable=False)
    match_percentage: Mapped[float] = mapped_column(nullable=False)
    # Semantic (cosine >= 0.70) matched/missing skills, computed ONCE at refresh time.
    # Persisted here so read paths never recompute embeddings and stay consistent
    # with the score. Nullable so existing rows / older refreshes don't break reads.
    matched_skills: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    missing_skills: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")
    internship = relationship("Internship", back_populates="recommendations")

    __table_args__ = (
        UniqueConstraint("user_id", "internship_id", name="uq_recommendations_user_internship"),
        Index("idx_recommendations_user_id",    "user_id"),
        Index("idx_recommendations_score",      "similarity_score"),
        Index("idx_recommendations_user_match", "user_id", "match_percentage"),  # stats high_match query
    )
