from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent_state import AgentState
from app.models.resume import Resume
from app.models.skill_snapshot import SkillSnapshot
from app.schemas.career import CareerPathsResponse, RoleComparisonRequest, RoleComparisonResponse
from app.services.auth_service import AuthService
from app.services.career_path_predictor import CareerPathPredictor
from app.services.role_comparator import RoleComparator

router = APIRouter(tags=["career"])
security = HTTPBearer()


@router.get("/career/paths", response_model=CareerPathsResponse)
async def career_paths(
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
            detail="Upload a resume to get career path predictions.",
        )

    predictor = CareerPathPredictor(db)
    paths = predictor.get_paths_for_user(user.id)
    current_level = predictor._determine_level(predictor._get_experience_count(user.id))

    # Generate AI insights for each path
    from app.services.career_ai_service import generate_career_insights
    paths_data = [
        {
            "path_id": p.path_id,
            "title": p.title,
            "match_percentage": p.match_percentage,
            "user_has": p.user_has,
            "user_missing": p.user_missing,
        }
        for p in paths
    ]
    ai_insights = generate_career_insights(
        user_skills=predictor._get_user_skills(user.id),
        career_paths=paths_data,
    )

    # Attach AI insights to each path
    for path in paths:
        insight = ai_insights.get(path.path_id, {})
        path.salary_range = insight.get("salary_range", "₹6-20 LPA")
        path.growth_rate = insight.get("growth_rate", "+18%")
        path.open_positions = insight.get("open_positions", 12000)
        path.why_fits = insight.get("why_fits", "")
        path.top_skill_to_learn = insight.get("top_skill_to_learn", "")

    return {
        "career_paths": paths,
        "current_level": current_level,
        "total": len(paths),
    }


@router.post("/career/compare", response_model=RoleComparisonResponse)
async def compare_roles(
    payload: RoleComparisonRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if len(payload.internship_ids) < 2 or len(payload.internship_ids) > 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide between 2 and 4 internship IDs.")

    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    comparator = RoleComparator(db)
    try:
        result = comparator.compare(payload.internship_ids, user.id)
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("Internship"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    return {
        "roles": result.roles,
        "common_skills": result.common_skills,
        "unique_skills": result.unique_skills,
        "total_roles_compared": len(result.roles),
    }


@router.get("/skills/snapshots")
async def skill_snapshots(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    snapshots = (
        db.query(SkillSnapshot)
        .filter(SkillSnapshot.user_id == user.id)
        .order_by(SkillSnapshot.snapshot_date.desc())
        .limit(100)
        .all()
    )

    return {
        "snapshots": [
            {
                "skill_name": s.skill_name,
                "frequency_pct": s.frequency_pct,
                "trend": s.trend,
                "snapshot_date": s.snapshot_date,
            }
            for s in snapshots
        ],
        "total": len(snapshots),
    }


@router.get("/skills/trends")
async def skill_trends(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    latest_date = (
        db.query(func.max(SkillSnapshot.snapshot_date))
        .filter(SkillSnapshot.user_id == user.id)
        .scalar()
    )
    if not latest_date:
        return {"trends": [], "snapshot_date": None, "insight": "Run the agent system to generate trend insights."}

    rows = (
        db.query(SkillSnapshot)
        .filter(SkillSnapshot.user_id == user.id, SkillSnapshot.snapshot_date == latest_date)
        .all()
    )

    state = db.query(AgentState).filter(AgentState.user_id == user.id).first()
    insight = "Run the agent system to generate trend insights."
    if state and state.state_json:
        insight = state.state_json.get("analyst_output", {}).get("insight", insight)

    return {
        "trends": [
            {
                "skill_name": r.skill_name,
                "frequency_pct": r.frequency_pct,
                "trend": r.trend,
                "snapshot_date": r.snapshot_date,
            }
            for r in rows
        ],
        "snapshot_date": str(latest_date),
        "insight": insight,
    }



