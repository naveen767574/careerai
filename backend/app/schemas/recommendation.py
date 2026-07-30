from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class RecommendationItem(BaseModel):
    internship_id: int
    title: str
    company: str
    location: str
    application_url: str
    source: str = ""
    similarity_score: float
    match_percentage: float
    display_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    match_label: str
    signal_breakdown: Optional[dict] = None
    # Added: lets the frontend compute "New This Week" without a separate call
    internship_created_at: Optional[str] = None

    class Config:
        from_attributes = True


class RecommendationsResponse(BaseModel):
    recommendations: list[RecommendationItem]
    total: int
    generated_at: str


class RefreshResponse(BaseModel):
    recommendations: list[RecommendationItem]
    count: int
    message: str


class SkillGapItem(BaseModel):
    skill: str
    frequency: int
    relevance: float
    priority: str


class SkillGapResponse(BaseModel):
    missing_skills: list[SkillGapItem]
    strong_skills: list[str]
    top_match_count: int
    message: str
