from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    NEW_RECOMMENDATIONS = "NEW_RECOMMENDATIONS"
    APPLICATION_UPDATE = "APPLICATION_UPDATE"
    RESUME_ANALYZED = "RESUME_ANALYZED"
    INTERVIEW_REPORT_READY = "INTERVIEW_REPORT_READY"
    LINKEDIN_REPORT_READY = "LINKEDIN_REPORT_READY"
    COACHING_BRIEF = "COACHING_BRIEF"
    SYSTEM_UPDATE = "SYSTEM_UPDATE"


class NotificationOut(BaseModel):
    id: int
    type: NotificationType
    title: str
    message: str
    is_read: bool
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    notifications: list[NotificationOut]
    total: int
    unread_count: int


class MarkReadResponse(BaseModel):
    message: str
    updated: int
