from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cover_letter_draft import CoverLetterDraft
from app.models.internship import Internship
from app.schemas.draft import DraftGenerateRequest, DraftListResponse, DraftOut, DraftUpdateRequest
from app.services.auth_service import AuthService
from app.agents.writer_agent import WriterAgent

router = APIRouter(prefix="/drafts", tags=["drafts"])
security = HTTPBearer()


@router.post("/generate", response_model=DraftOut, status_code=status.HTTP_201_CREATED)
async def generate_draft(
    payload: DraftGenerateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    try:
        output = WriterAgent(db).draft(user.id, payload.internship_id)
    except ValueError as exc:
        detail = str(exc)
        if "Internship" in detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc

    draft = db.query(CoverLetterDraft).filter(CoverLetterDraft.id == output.draft_id).first()
    return draft


@router.get("", response_model=DraftListResponse)
async def list_drafts(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    drafts = (
        db.query(CoverLetterDraft)
        .filter(CoverLetterDraft.user_id == user.id)
        .order_by(CoverLetterDraft.created_at.desc())
        .all()
    )
    return {"drafts": drafts, "total": len(drafts)}


@router.patch("/{draft_id}", response_model=DraftOut)
async def update_draft(
    draft_id: int,
    payload: DraftUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    draft = db.query(CoverLetterDraft).filter(CoverLetterDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    if draft.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your draft")

    if payload.content is not None:
        draft.content = payload.content
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.patch("/{draft_id}/approve", response_model=DraftOut)
async def approve_draft(
    draft_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    draft = db.query(CoverLetterDraft).filter(CoverLetterDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    if draft.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your draft")

    draft.status = "approved"
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/{draft_id}")
async def discard_draft(
    draft_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    draft = db.query(CoverLetterDraft).filter(CoverLetterDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    if draft.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your draft")

    draft.status = "discarded"
    db.add(draft)
    db.commit()
    return {"message": "Draft discarded"}
