from datetime import datetime

from pydantic import BaseModel


class StartSessionResponse(BaseModel):
    session_id: str
    step: int
    question: str


class AnswerRequest(BaseModel):
    session_id: str
    message: str


class BuilderStepResponse(BaseModel):
    session_id: str
    step: int
    question: str
    resume_data_summary: dict


class TemplateOut(BaseModel):
    template_id: str
    name: str
    description: str
    best_for: list[str]
    preview_color: str
    recommended: bool = False


class ATSScoreOut(BaseModel):
    total_score: int
    structure_score: int
    keyword_score: int
    completeness_score: int
    feedback: list[str]


class ResumeVersionOut(BaseModel):
    id: int
    version_number: int
    template_name: str | None
    ats_score: int | None
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class FinalizeResponse(BaseModel):
    message: str
    version_number: int
    ats_score: int
