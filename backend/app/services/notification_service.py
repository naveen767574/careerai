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


def create_notification(db: Session, user_id: int, type: str, title: str, message: str) -> Notification:
    return NotificationService(db).create_notification(user_id, type, title, message)
