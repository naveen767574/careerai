from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    internship_id = Column(Integer, ForeignKey("internships.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(30), nullable=False, default="saved")
    # status values: saved | applied | interview | offer | rejected | withdrawn
    notes = Column(Text, nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="applications")
    internship = relationship("Internship", back_populates="applications")

    __table_args__ = (
        UniqueConstraint("user_id", "internship_id", name="uq_application_user_internship"),
        # Composite index: fast filter for list_applications(user_id, status=...)
        # and stats saved count (user_id + status='saved')
    )

# SQLAlchemy Index objects referencing the Column instances must be declared
# outside the class when using the legacy Column() API.
from sqlalchemy import Index as _Idx
_Idx("idx_applications_user_id",     Application.user_id)
_Idx("idx_applications_user_status", Application.user_id, Application.status)
