from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.internship import Internship
from app.models.internship_skill import InternshipSkill
from app.models.recommendation import Recommendation
from app.models.resume import Resume
from app.models.skill import Skill
from app.schemas.recommendation import RecommendationsResponse, RefreshResponse, RecommendationItem
from app.services.auth_service import AuthService
from app.services.recommendation_engine import RecommendationEngine

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
security = HTTPBearer()


@router.get("", response_model=RecommendationsResponse)
async def get_recommendations(
    limit: int = Query(default=20, ge=1, le=20),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume found. Upload a resume to get recommendations.",
        )

    from app.models.recommendation import Recommendation as RecModel
    from app.models.internship import Internship

    saved_recs = db.query(RecModel).filter(
        RecModel.user_id == user.id
    ).order_by(RecModel.match_percentage.desc()).limit(50).all()

    items = []
    for r in saved_recs:
        internship = db.query(Internship).filter(Internship.id == r.internship_id).first()
        if not internship:
            continue
        items.append(RecommendationItem(
            internship_id=r.internship_id,
            title=internship.title or '',
            company=internship.company or '',
            location=internship.location or '',
            application_url=internship.application_url or '',
            similarity_score=r.similarity_score or 0.0,
            match_percentage=r.match_percentage or 0.0,
            matched_skills=[],
            missing_skills=[],
            match_label='Good',
        ))

    return {
        "recommendations": items,
        "total": len(items),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_recommendations(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume found. Upload a resume to get recommendations.",
        )

    engine = RecommendationEngine(db)
    engine.refresh_for_user(user.id)  # Just refresh, ignore return value

    # Now fetch the saved recommendations from DB to return
    from app.models.recommendation import Recommendation as RecModel
    from app.models.internship import Internship

    saved_recs = db.query(RecModel).filter(
        RecModel.user_id == user.id
    ).order_by(RecModel.match_percentage.desc()).limit(20).all()

    items = []
    for r in saved_recs:
        internship = db.query(Internship).filter(Internship.id == r.internship_id).first()
        if not internship:
            continue
        items.append(RecommendationItem(
            internship_id=r.internship_id,
            title=internship.title or '',
            company=internship.company or '',
            location=internship.location or '',
            application_url=internship.application_url or '',
            similarity_score=r.similarity_score or 0.0,
            match_percentage=r.match_percentage or 0.0,
            matched_skills=[],
            missing_skills=[],
            match_label='Good',
        ))

    return {"recommendations": items, "total": len(items), "count": len(items), "message": "Recommendations refreshed successfully"}


