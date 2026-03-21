from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ApplicationCreate(BaseModel):
    internship_id: int
    status: str = "saved"
    notes: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None


class ApplicationInternshipSummary(BaseModel):
    id: int
    title: str
    company: str
    location: Optional[str] = None

    class Config:
        from_attributes = True


class ApplicationOut(BaseModel):
    id: int
    internship: ApplicationInternshipSummary
    status: str
    notes: Optional[str]
    applied_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationListResponse(BaseModel):
    applications: list[ApplicationOut]
    total: int
