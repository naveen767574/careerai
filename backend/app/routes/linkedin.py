from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.linkedin import (
    HistoryResponse,
    LinkedInReportOut,
    ProfileInputRequest,
    RegenerateRequest,
    RegenerateResponse,
    ScoreResponse,
)
from app.services.auth_service import AuthService
from app.services.linkedin_service import LinkedInService


router = APIRouter(prefix="/linkedin", tags=["linkedin"])
security = HTTPBearer()


def get_current_user(db: Session, credentials: HTTPAuthorizationCredentials):
    try:
        return AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def _has_any_content(profile_input: dict) -> bool:
    if (profile_input.get("headline") or "").strip():
        return True
    if (profile_input.get("about") or "").strip():
        return True
    if (profile_input.get("education") or "").strip():
        return True
    if any(str(item).strip() for item in profile_input.get("experience", []) or []):
        return True
    if any(str(item).strip() for item in profile_input.get("skills", []) or []):
        return True
    if any(str(item).strip() for item in profile_input.get("projects", []) or []):
        return True
    if profile_input.get("has_photo") is True:
        return True
    return False


@router.post("/analyze", response_model=LinkedInReportOut, status_code=status.HTTP_201_CREATED)
async def analyze_profile(
    payload: ProfileInputRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    profile_input = payload.model_dump()
    if not _has_any_content(profile_input):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please paste at least one LinkedIn section to analyze.",
        )
    combined_text = " ".join([
        profile_input.get("headline", "") or "",
        profile_input.get("about", "") or "",
        profile_input.get("education", "") or "",
        " ".join(profile_input.get("experience", []) or []),
        " ".join(profile_input.get("projects", []) or []),
        " ".join(profile_input.get("skills", []) or []),
    ]).strip()
    if len(combined_text) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide at least 20 characters of LinkedIn content.",
        )
    user = get_current_user(db, credentials)
    report = LinkedInService(db).analyze(user.id, profile_input)
    return report


@router.get("/report/{session_id}", response_model=LinkedInReportOut)
async def get_report(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    report = LinkedInService(db).get_report(session_id, user.id)
    return {
        "session_id": report.session_id,
        "profile_score": report.profile_score,
        "score_breakdown": report.score_breakdown,
        "gap_analysis": report.gap_analysis,
        "headline_variants": report.headline_variants,
        "about_section": report.about_section,
        "experience_improvements": report.experience_improvements,
        "skills_optimization": report.skills_optimization,
        "improvement_priority": report.improvement_priority,
        "created_at": report.created_at,
    }


@router.post("/regenerate", response_model=RegenerateResponse)
async def regenerate_section(
    payload: RegenerateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if payload.section not in {"headline", "about", "bullets"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid section")
    user = get_current_user(db, credentials)
    result = LinkedInService(db).regenerate_section(payload.session_id, user.id, payload.section, payload.feedback)
    return result


@router.get("/score/{session_id}", response_model=ScoreResponse)
async def get_score(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    result = LinkedInService(db).get_score(session_id, user.id)
    return result


@router.get("/history", response_model=HistoryResponse)
async def history(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    sessions = LinkedInService(db).get_history(user.id)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/latest")
async def latest(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    report = LinkedInService(db).get_latest(user.id)
    if not report:
        return {"report": None}
    return report
