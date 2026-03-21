from datetime import datetime

from pydantic import BaseModel


class StartInterviewRequest(BaseModel):
    internship_id: int


class QuestionOut(BaseModel):
    id: int
    order_index: int
    question_text: str
    category: str
    difficulty: str | None
    skill_tested: str | None

    class Config:
        from_attributes = True


class StartInterviewResponse(BaseModel):
    session_id: str
    internship: dict
    first_question: QuestionOut
    total_questions: int


class SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: int
    answer_text: str


class AnswerFeedback(BaseModel):
    answer_saved: bool
    score: float
    verdict: str
    strengths: list[str]
    weaknesses: list[str]
    model_answer: str
    improvement_tip: str
    next_question: QuestionOut | None
    answers_submitted: int
    total_questions: int


class ReportOut(BaseModel):
    session_id: str
    internship_id: int
    overall_score: float
    technical_score: float
    behavioral_score: float
    readiness_level: str
    readiness_message: str
    top_strengths: list[str]
    top_improvements: list[str]
    recommended_resources: list[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SessionSummary(BaseModel):
    session_id: str
    internship_title: str
    company: str
    status: str
    overall_score: float | None
    readiness_level: str | None
    created_at: datetime


class HistoryResponse(BaseModel):
    sessions: list[SessionSummary]
    total: int
