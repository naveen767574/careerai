from datetime import date, datetime
from typing import List

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
    search_scores: dict[str, float] = {}
    is_search: bool = False


class InternshipDetailResponse(BaseModel):
    internship: InternshipOut
    required_skills: list[str]


class SkillGapResponse(BaseModel):
    matched_skills: list[str]
    missing_skills: list[str]
    match_percentage: float


class SkillSimulation(BaseModel):
    """What-if result for a single missing skill."""
    skill: str
    simulated_pct: float       # projected match % if this skill were added
    delta_pct: float           # how many percentage points it would add
    new_label: str             # e.g. "Strong Match"


class SkillSimulationsResponse(BaseModel):
    current_pct: float
    simulations: list[SkillSimulation]


class MatchExplanation(BaseModel):
    match_reasons: List[str]
    missing_skills: List[str]
    tip: str


class CategorizedMissingSkills(BaseModel):
    """Missing skills grouped by importance weight."""
    core: list[str] = []
    secondary: list[str] = []
    optional: list[str] = []


class SkillImpact(BaseModel):
    """Projected match-% gain from adding one missing skill."""
    skill: str
    impact: float


class MatchInsightsResponse(BaseModel):
    """
    Role-aware, stack-aware match insight bundle for a single internship+user.

    match_percentage is the SAME weighted skill-coverage score returned by
    /skill-gap and /recommendations — this endpoint enriches it, it never forks
    a second score.
    """
    role_type: str
    role_label: str
    stack_type: str
    stack_label: str
    match_percentage: float
    matched_skills: list[str]
    missing_skills: CategorizedMissingSkills
    explanation: str
    # Per-skill "why you match" bullets — each maps to ONE real matched skill and
    # explains HOW it helps in THIS role. Empty when there are no matched skills.
    match_reasons: list[str] = []
    recommendation: str
    top_missing_skill: str
    skill_impacts: list[SkillImpact]

