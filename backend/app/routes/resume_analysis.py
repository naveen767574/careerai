from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.resume import Resume
from app.models.resume_analysis import ResumeAnalysis
from app.services.auth_service import AuthService

router = APIRouter()
security = HTTPBearer()


@router.get("/resume/{resume_id}/analysis")
async def get_resume_analysis(
    resume_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    analysis = (
        db.query(ResumeAnalysis)
        .filter(ResumeAnalysis.resume_id == resume_id, ResumeAnalysis.user_id == user.id)
        .order_by(ResumeAnalysis.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    return {
        "id": analysis.id,
        "resume_id": str(analysis.resume_id),
        "ats_score": analysis.ats_score,
        "extracted_skills": analysis.extracted_skills or [],
        "missing_sections": analysis.missing_sections or [],
        "analysis": analysis.analysis_json or {},
        "created_at": analysis.created_at,
    }
