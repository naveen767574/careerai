from pydantic import BaseModel


class CareerStepOut(BaseModel):
    level: str
    skills_to_acquire: list[str]


class CareerPathOut(BaseModel):
    path_id: str
    title: str
    description: str
    alignment_score: float
    match_percentage: float
    required_skills: list[str]
    user_has: list[str]
    user_missing: list[str]
    current_level: str
    timeline: str
    steps: list[CareerStepOut]
    salary_range: str = "₹6-20 LPA"
    growth_rate: str = "+18%"
    open_positions: int = 12000
    why_fits: str = ""
    top_skill_to_learn: str = ""


class CareerPathsResponse(BaseModel):
    career_paths: list[CareerPathOut]
    current_level: str
    total: int


class RoleComparisonItemOut(BaseModel):
    internship_id: int
    title: str
    company: str
    location: str
    required_skills: list[str]
    user_match_percentage: float
    matched_skills: list[str]
    missing_skills: list[str]


class RoleComparisonRequest(BaseModel):
    internship_ids: list[int]


class RoleComparisonResponse(BaseModel):
    roles: list[RoleComparisonItemOut]
    common_skills: list[str]
    unique_skills: dict[int, list[str]]
    total_roles_compared: int

