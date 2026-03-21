from pydantic import BaseModel
from datetime import datetime


class ProfileInputRequest(BaseModel):
    headline: str = ""
    about: str = ""
    experience: list[str] = []
    skills: list[str] = []
    projects: list[str] = []
    education: str = ""
    has_photo: bool = False


class HeadlineVariants(BaseModel):
    keyword_rich: str
    achievement_led: str
    role_focused: str


class ScoreBreakdown(BaseModel):
    headline: int
    about: int
    experience: int
    skills: int
    projects: int
    education: int
    photo: int


class LinkedInReportOut(BaseModel):
    session_id: str
    profile_score: int
    score_breakdown: dict
    gap_analysis: dict
    headline_variants: dict
    about_section: str | None
    experience_improvements: dict | None
    skills_optimization: dict | None
    improvement_priority: list[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ScoreResponse(BaseModel):
    session_id: str
    profile_score: int
    score_breakdown: dict
    improvement_priority: list[str]


class RegenerateRequest(BaseModel):
    session_id: str
    section: str
    feedback: str


class RegenerateResponse(BaseModel):
    section: str
    updated_content: dict | str


class SessionSummary(BaseModel):
    session_id: str
    profile_score: int | None
    status: str
    created_at: datetime


class HistoryResponse(BaseModel):
    sessions: list[SessionSummary]
    total: int
