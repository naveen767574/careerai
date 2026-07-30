from pydantic import BaseModel
from datetime import datetime


# Legacy enum kept for reference — not used in NotificationOut to allow
# free-form type strings (e.g. "job_alert") without breaking validation.
NOTIFICATION_TYPES = [
    "NEW_RECOMMENDATIONS",
    "APPLICATION_UPDATE",
    "RESUME_ANALYZED",
    "INTERVIEW_REPORT_READY",
    "LINKEDIN_REPORT_READY",
    "COACHING_BRIEF",
    "SYSTEM_UPDATE",
    "job_alert",
]


class NotificationOut(BaseModel):
    id: int
    type: str          # free-form string — avoids enum mismatch for "job_alert" etc.
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
