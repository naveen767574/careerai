from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def create_notification(self, user_id: int, type: str, title: str, message: str) -> Notification:
        expires_at = datetime.utcnow() + timedelta(days=30)
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            expires_at=expires_at,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_user_notifications(self, user_id: int) -> list[Notification]:
        now = datetime.utcnow()
        return (
            self.db.execute(
                select(Notification)
                .where(Notification.user_id == user_id, Notification.expires_at > now)
                .order_by(Notification.created_at.desc())
            )
            .scalars()
            .all()
        )

    def mark_as_read(self, notification_id: int, user_id: int) -> Notification:
        notification = (
            self.db.execute(
                select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
            )
            .scalar_one_or_none()
        )
        if not notification:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        notification.is_read = True
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_all_as_read(self, user_id: int) -> int:
        result = self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
        self.db.commit()
        return result.rowcount or 0

    def delete_expired(self) -> int:
        now = datetime.utcnow()
        result = self.db.execute(delete(Notification).where(Notification.expires_at < now))
        self.db.commit()
        return result.rowcount or 0

    def get_unread_count(self, user_id: int) -> int:
        now = datetime.utcnow()
        return (
            self.db.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id, Notification.is_read == False, Notification.expires_at > now)
            )
            .scalar_one()
        )


    def create_job_alert_if_new(
        self,
        user_id: int,
        internship_id: int,
        title: str,
        company: str,
        match_pct: float,
        matched_skills: list[str] | None = None,
    ) -> bool:
        """
        Create a job-alert notification for a high-match internship.

        Deduplicates by internship ID (type = "job_alert:{internship_id}") so
        that the check is immune to title/company changes on re-scrape.
        One alert per user per internship, ever.
        Returns True if a new notification was created, False if one already exists.

        This is intentionally called AFTER the recommendation commit so the
        notification batch can be rolled back independently without breaking
        the recommendation data.
        """
        # Stable, internship-scoped type key — immune to title/company renames.
        alert_type = f"job_alert:{internship_id}"

        existing = (
            self.db.execute(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.type == alert_type,
                )
            )
            .scalar_one_or_none()
        )
        if existing:
            return False

        label = "Excellent" if match_pct >= 80 else "Strong" if match_pct >= 70 else "Good"
        notif_title = f"New Match: {title} at {company}"

        # Build message — include top matched skills when available.
        skills_snippet = ""
        if matched_skills:
            top = matched_skills[:4]
            skills_snippet = f" Matched skills: {', '.join(top)}."

        message = (
            f"{label} match ({match_pct:.0f}%) — {title} at {company} looks like a "
            f"great fit for your profile.{skills_snippet} Check it out on the Internships page."
        )
        self.create_notification(
            user_id=user_id,
            type=alert_type,
            title=notif_title,
            message=message,
        )
        return True


def create_notification(db: Session, user_id: int, type: str, title: str, message: str) -> Notification:
    return NotificationService(db).create_notification(user_id, type, title, message)
