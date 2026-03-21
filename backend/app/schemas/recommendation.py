from datetime import datetime
from pydantic import BaseModel


class RecommendationItem(BaseModel):
    internship_id: int
    title: str
    company: str
    location: str
    application_url: str
    similarity_score: float
    match_percentage: float
    matched_skills: list[str]
    missing_skills: list[str]
    match_label: str

    class Config:
        from_attributes = True


class RecommendationsResponse(BaseModel):
    recommendations: list[RecommendationItem]
    total: int
    generated_at: datetime


class RefreshResponse(BaseModel):
    recommendations: list[RecommendationItem]
    count: int
    message: str
