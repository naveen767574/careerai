from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.chat import BoltChatResponse, ChatHistoryResponse, ChatMessage
from app.services.auth_service import AuthService
from app.services.bolt_service import BoltAIService

router = APIRouter(prefix="/bolt", tags=["bolt"])
security = HTTPBearer()


@router.post("/chat", response_model=BoltChatResponse)
async def chat(
    payload: ChatMessage,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")
    if len(message) > 2000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message too long (max 2000 characters)")

    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    service = BoltAIService(db)
    response_text, intent, used_session_id = service.process_message(user.id, message, payload.session_id)

    return {
        "response": response_text,
        "intent": intent,
        "session_id": used_session_id,
    }


@router.get("/history", response_model=ChatHistoryResponse)
async def history(
    session_id: str = Query(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    service = BoltAIService(db)
    messages = service.get_session_history(user.id, session_id)
    return {"session_id": session_id, "messages": messages, "total": len(messages)}


@router.delete("/history/{session_id}")
async def delete_history(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    service = BoltAIService(db)
    deleted = service.delete_session(user.id, session_id)
    return {"message": "Session deleted", "deleted": deleted}

