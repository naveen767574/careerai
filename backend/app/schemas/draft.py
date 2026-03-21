from pydantic import BaseModel
from datetime import datetime


class DraftInternshipSummary(BaseModel):
    id: int
    title: str
    company: str

    class Config:
        from_attributes = True


class DraftOut(BaseModel):
    id: int
    internship: DraftInternshipSummary
    content: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DraftUpdateRequest(BaseModel):
    content: str | None = None


class DraftGenerateRequest(BaseModel):
    internship_id: int


class DraftListResponse(BaseModel):
    drafts: list[DraftOut]
    total: int
