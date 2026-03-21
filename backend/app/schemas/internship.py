from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class InternshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str
    location: str
    description: str
    application_url: str
    source: str
    posted_date: date | None
    salary_range: str | None
    is_active: bool
    created_at: datetime


class InternshipListResponse(BaseModel):
    internships: list[InternshipOut]
    total: int
    page: int
    pages: int


class InternshipDetailResponse(BaseModel):
    internship: InternshipOut
    required_skills: list[str]


class SkillGapResponse(BaseModel):
    matched_skills: list[str]
    missing_skills: list[str]
    match_percentage: float
