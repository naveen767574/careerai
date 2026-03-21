from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Optional


class BoltIntent(str, Enum):
    NAVIGATION = "navigation"
    RESUME_COACH = "resume_coach"
    JOB_SEARCH = "job_search"
    CAREER_MENTOR = "career_mentor"
    SKILL_ADVISOR = "skill_advisor"


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatMessageOut(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    intent: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class BoltChatResponse(BaseModel):
    response: str
    intent: BoltIntent
    session_id: str


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessageOut]
    total: int
