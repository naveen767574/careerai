from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.notification import NotificationListResponse, NotificationOut, MarkReadResponse
from app.services.auth_service import AuthService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])
security = HTTPBearer()


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    service = NotificationService(db)
    notifications = service.get_user_notifications(user.id)
    unread = service.get_unread_count(user.id)

    return {
        "notifications": notifications,
        "total": len(notifications),
        "unread_count": unread,
    }


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    service = NotificationService(db)
    return service.mark_as_read(notification_id, user.id)


@router.patch("/read-all", response_model=MarkReadResponse)
async def read_all(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    service = NotificationService(db)
    updated = service.mark_all_as_read(user.id)
    return {"message": "All notifications marked as read", "updated": updated}
