import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.internship import Internship
from app.models.recommendation import Recommendation
from app.models.resume import Resume
from app.models.skill import Skill
from app.schemas.explanation import ExplanationResponse
from app.schemas.recommendation import (
    RecommendationItem,
    RecommendationsResponse,
    RefreshResponse,
    SkillGapItem,
    SkillGapResponse,
)
from app.services.auth_service import AuthService
from app.services.event_logger import (
    log_event,
    EVENT_RECOMMENDATIONS_SERVED,
)
from app.services.explanation_service import generate_explanation
from app.services.recommendation_engine import RecommendationEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
security = HTTPBearer()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_match_label(raw_percentage: float) -> str:
    """
    Derive label from the stored match percentage (0–100 range).
    This is weighted skill COVERAGE (real matched/total), so the thresholds map
    to honest overlap, not a compressed composite.
    """
    if raw_percentage >= 80:
        return "Excellent Match"
    if raw_percentage >= 70:
        return "Strong Match"
    if raw_percentage >= 60:
        return "Good Match"
    if raw_percentage >= 50:
        return "Partial Match"
    return "Low Match"


def _get_user_skill_names(db: Session, user_id: int) -> list[str]:
    """Fetch user's skills as a normalized list (free-text LLM context only)."""
    rows = db.query(Skill.skill_name).filter(Skill.user_id == user_id).all()
    return [row[0].strip().lower() for row in rows if row[0]]


def _build_recommendation_item(
    rec: Recommendation,
    internship: Internship,
) -> RecommendationItem:
    """
    Build a RecommendationItem from a DB Recommendation row + its Internship.

    matched_skills / missing_skills are read VERBATIM from the row — they were
    computed semantically (cosine >= 0.70) at refresh time. No recompute here,
    so the chips always agree with the score and reads stay fast.
    """
    matched = rec.matched_skills or []
    missing = rec.missing_skills or []

    raw_pct = rec.match_percentage or 0.0
    label = _derive_match_label(raw_pct)

    # Serialize internship created_at so the frontend can compute "New This Week"
    created_iso = (
        internship.created_at.isoformat()
        if internship.created_at is not None
        else None
    )

    return RecommendationItem(
        internship_id=rec.internship_id,
        title=internship.title or "",
        company=internship.company or "",
        location=internship.location or "",
        application_url=internship.application_url or "",
        source=internship.source or "",
        similarity_score=round(rec.similarity_score or 0.0, 4),
        match_percentage=raw_pct,
        display_score=raw_pct,
        matched_skills=matched,
        missing_skills=missing,
        match_label=label,
        internship_created_at=created_iso,
    )


# ---------------------------------------------------------------------------
# GET /api/recommendations
# Reads from DB cache — fast, always available.
# Run POST /refresh to recompute scores.
# ---------------------------------------------------------------------------

@router.get("", response_model=RecommendationsResponse)
async def get_recommendations(
    limit: int = Query(default=20, ge=1, le=20),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    t_start = time.time()

    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume found. Upload a resume to get recommendations.",
        )

    # FIX: use joinedload to fetch recommendations + internships in ONE query
    # instead of N+1 individual internship lookups
    saved_recs = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == user.id)
        .options(joinedload(Recommendation.internship))
        .order_by(Recommendation.match_percentage.desc())
        .limit(limit)
        .all()
    )

    if not saved_recs:
        # No cached recommendations — tell frontend to call /refresh
        return RecommendationsResponse(
            recommendations=[],
            total=0,
            generated_at=datetime.utcnow().isoformat(),
        )

    items = []
    for rec in saved_recs:
        if not rec.internship:
            continue
        item = _build_recommendation_item(rec, rec.internship)
        items.append(item)

    elapsed = round((time.time() - t_start) * 1000)
    logger.info(
        "recommendations.get user_id=%d count=%d elapsed_ms=%d",
        user.id, len(items), elapsed,
    )

    # Phase 0: record what was shown and in what order (exposure signal).
    # Emitted after the payload is built so instrumentation is off the hot path.
    log_event(
        EVENT_RECOMMENDATIONS_SERVED,
        user_id=user.id,
        payload={
            "shown": [
                {
                    "internship_id": it.internship_id,
                    "match_pct": it.match_percentage,
                    "rank": rank,
                }
                for rank, it in enumerate(items, start=1)
            ]
        },
    )

    return RecommendationsResponse(
        recommendations=items,
        total=len(items),
        generated_at=datetime.utcnow().isoformat(),
    )


# ---------------------------------------------------------------------------
# POST /api/recommendations/refresh
# Runs the full recommendation engine, recomputes scores, saves to DB.
# Called when: user uploads new resume, user adds skills, manual refresh.
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=RefreshResponse)
async def refresh_recommendations(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    t_start = time.time()

    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume found. Upload a resume to get recommendations.",
        )

    # Run the full multi-agent scoring pipeline
    engine = RecommendationEngine(db)
    result = engine.refresh_for_user(user.id)
    count = result.get("recommendations", 0)

    # Now read back what was saved (same pattern as GET — consistent response)
    saved_recs = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == user.id)
        .options(joinedload(Recommendation.internship))
        .order_by(Recommendation.match_percentage.desc())
        .limit(20)
        .all()
    )

    items = []
    for rec in saved_recs:
        if not rec.internship:
            continue
        item = _build_recommendation_item(rec, rec.internship)
        items.append(item)

    elapsed = round((time.time() - t_start) * 1000)
    logger.info(
        "recommendations.refresh user_id=%d scored=%d returned=%d elapsed_ms=%d",
        user.id, count, len(items), elapsed,
    )

    return RefreshResponse(
        recommendations=items,
        count=len(items),
        message=f"Recommendations refreshed. Found {len(items)} matches.",
    )


# ---------------------------------------------------------------------------
# GET /api/recommendations/skill-gap
#
# Analyzes the user's top recommendations and tells them:
# - Which skills they're missing most often (prioritized)
# - Which skills they already have that are in demand
# - Actionable priority ranking
#
# This runs entirely from DB + user skills — no engine call needed.
# ---------------------------------------------------------------------------

@router.get("/skill-gap", response_model=SkillGapResponse)
async def get_skill_gap(
    top_n: int = Query(default=10, ge=3, le=20, description="Analyze top N recommendations"),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    # Get user's top N recommendations from DB
    top_recs = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == user.id)
        .order_by(Recommendation.match_percentage.desc())
        .limit(top_n)
        .all()
    )

    if not top_recs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendations found. Run /refresh first.",
        )

    # Aggregate across the top recommendations using the STORED semantic
    # matched/missing skills (cosine >= 0.70), computed at refresh time.
    # No exact string matching, no embedding recompute here.
    # missing_tracker: skill → list of match_percentages of jobs that need it
    missing_tracker: dict[str, list[float]] = defaultdict(list)
    strong_tracker: dict[str, int] = defaultdict(int)

    for rec in top_recs:
        score = rec.match_percentage or 0.0

        for skill in (rec.matched_skills or []):
            strong_tracker[skill] += 1
        for skill in (rec.missing_skills or []):
            missing_tracker[skill].append(score)

    # Build SkillGapItems — ranked by frequency × average relevance
    gap_items: list[SkillGapItem] = []
    for skill, scores in missing_tracker.items():
        frequency = len(scores)
        relevance = round(sum(scores) / len(scores) / 100.0, 3)  # normalize to 0–1

        # Priority logic:
        # High   = missing from 3+ jobs OR from a high-scoring match (>70%)
        # Medium = missing from 2 jobs
        # Low    = missing from only 1 job
        if frequency >= 3 or (frequency >= 1 and max(scores) > 70):
            priority = "High"
        elif frequency == 2:
            priority = "Medium"
        else:
            priority = "Low"

        gap_items.append(SkillGapItem(
            skill=skill,
            frequency=frequency,
            relevance=relevance,
            priority=priority,
        ))

    # Sort: High priority first, then by frequency desc, then relevance desc
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    gap_items.sort(key=lambda x: (priority_order[x.priority], -x.frequency, -x.relevance))

    # Strong skills = user skills that appear in 2+ top matches
    strong_skills = [
        skill for skill, count in strong_tracker.items() if count >= 2
    ]
    strong_skills.sort(key=lambda s: -strong_tracker[s])

    # Human-readable summary
    high_priority = [g for g in gap_items if g.priority == "High"]
    if high_priority:
        top_missing = ", ".join(g.skill for g in high_priority[:3])
        message = (
            f"To improve your matches, focus on: {top_missing}. "
            f"These appear in {high_priority[0].frequency}+ of your top opportunities."
        )
    elif gap_items:
        message = "You're well-matched for your top opportunities. A few skills could improve your reach."
    else:
        message = "Great profile! You already have all the key skills for your top matches."

    return SkillGapResponse(
        missing_skills=gap_items,
        strong_skills=strong_skills[:10],
        top_match_count=len(top_recs),
        message=message,
    )


# ---------------------------------------------------------------------------
# POST /api/recommendations/explain/{internship_id}
# Returns a GROUNDED explanation for a specific recommendation (Phase 3).
# Called on-demand (user clicks "Why this match?") — NEVER on list load.
#
# The explanation layer may only talk ABOUT matched/missing skills that were
# already computed deterministically at refresh time. `display_score` is passed
# straight through from the stored recommendation row; nothing here recomputes
# or adjusts it.
# ---------------------------------------------------------------------------

@router.post("/explain/{internship_id}", response_model=ExplanationResponse)
async def explain_recommendation(
    internship_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    # Verify this recommendation exists for this user
    rec = (
        db.query(Recommendation)
        .filter(
            Recommendation.user_id == user.id,
            Recommendation.internship_id == internship_id,
        )
        .first()
    )
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found.",
        )

    internship = db.query(Internship).filter(Internship.id == internship_id).first()
    if not internship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found.")

    # Use the STORED semantic matched/missing from the recommendation row
    # (cosine >= 0.70, computed at refresh). No recompute — consistent with score.
    matched = rec.matched_skills or []
    missing = rec.missing_skills or []

    # DETERMINISTIC score — read from storage, never regenerated here.
    raw_pct = rec.match_percentage or 0.0

    explanation, source = generate_explanation(
        db=db,
        user_id=user.id,
        job=internship,
        matched_skills=matched,
        missing_skills=missing,
        score=raw_pct,
    )

    return ExplanationResponse(
        internship_id=internship_id,
        title=internship.title,
        company=internship.company,
        match_score=raw_pct,
        match_label=_derive_match_label(raw_pct),
        matched_skills=[s for s in matched],
        missing_skills=[s for s in missing],
        explanation=explanation,
        source=source,
    )
