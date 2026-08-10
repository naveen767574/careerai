from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.internship import Internship
from app.models.internship_skill import InternshipSkill
from app.models.recommendation import Recommendation
from app.models.resume import Resume
from app.models.skill import Skill
from app.services.auth_service import AuthService
from app.services.event_logger import (
    log_event,
    EVENT_MATCH_VIEWED,
    EVENT_WHATIF_SIMULATED,
)
from app.schemas.explanation import ExplanationResponse
from app.schemas.internship import (
    InternshipDetailResponse,
    InternshipListResponse,
    InternshipOut,
    MatchInsightsResponse,
    SkillGapResponse,
    SkillSimulation,
    SkillSimulationsResponse,
)
from app.services.explanation_service import generate_explanation
from app.services.recommendation_engine import (
    SKILL_WEIGHTS,
    SkillClassifier,
    _derive_match_label,
    _normalize,
)

router = APIRouter(prefix="/internships", tags=["internships"])
security = HTTPBearer()


@router.get("", response_model=InternshipListResponse)
async def list_internships(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    location: str = "",
    company: str = "",
    search: str = "",
    db: Session = Depends(get_db),
):
    # --- SEMANTIC SEARCH (when search query provided) ---
    if search and search.strip():
        try:
            from app.services.embedding_service import embed_query
            query_vector = embed_query(search.strip())
            vector_str = "[" + ",".join(map(str, query_vector)) + "]"

            # Use pgvector cosine distance to find semantically similar internships
            # <=> operator means cosine distance (lower = more similar)
            sql = text("""
                SELECT id, 1 - (embedding <=> CAST(:vec AS vector)) as similarity
                FROM internships
                WHERE is_active = true
                AND embedding IS NOT NULL
                AND 1 - (embedding <=> CAST(:vec AS vector)) > 0.2
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :limit OFFSET :offset
            """)
            count_sql = text("""
                SELECT COUNT(*) FROM internships
                WHERE is_active = true
                AND embedding IS NOT NULL
                AND 1 - (embedding <=> CAST(:vec AS vector)) > 0.2
            """)

            rows = db.execute(sql, {
                "vec": vector_str,
                "limit": limit,
                "offset": (page - 1) * limit
            }).fetchall()

            if not rows:
                raise ValueError("No semantic matches found, falling back to keyword search")

            total = db.execute(count_sql, {"vec": vector_str}).scalar() or 0
            pages = ceil(total / limit) if total else 1

            # Fetch full internship objects and attach similarity score
            results = []
            for row in rows:
                internship = db.query(Internship).filter(Internship.id == row.id).first()
                if internship:
                    # Attach similarity score to the object temporarily
                    internship._similarity = round(float(row.similarity) * 100, 1)
                    results.append(internship)

            return {
                "internships": [InternshipOut.model_validate(i) for i in results],
                "total": total,
                "page": page,
                "pages": pages,
                "search_scores": {str(row.id): round(float(row.similarity) * 100, 1) for row in rows},
                "is_search": True,
            }

        except Exception as e:
            # If semantic search fails, fall through to keyword search
            print(f"Semantic search failed, falling back to keyword search: {e}")

    # --- STANDARD SEARCH (no query or semantic search failed) ---
    query = db.query(Internship).filter(Internship.is_active == True)

    if location:
        query = query.filter(Internship.location.ilike(f"%{location}%"))
    if company:
        query = query.filter(Internship.company.ilike(f"%{company}%"))
    if search:
        query = query.filter(
            or_(
                Internship.title.ilike(f"%{search}%"),
                Internship.description.ilike(f"%{search}%"),
            )
        )

    total = query.count()
    pages = ceil(total / limit) if total else 1
    internships = (
        query.order_by(Internship.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "internships": [InternshipOut.model_validate(i) for i in internships],
        "total": total,
        "page": page,
        "pages": pages,
        "search_scores": {},
        "is_search": False,
    }


# ---------------------------------------------------------------------------
# GET /api/internships/stats
# Returns four stat values for the Internships page header strip.
# All counts are computed with raw SQL to match exact DB state — no ORM
# datetime arithmetic that could drift from the DB clock.
# ---------------------------------------------------------------------------

import logging as _logging
_stats_logger = _logging.getLogger("internships.stats")


@router.get("/stats")
async def internship_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Returns:
      total_positions  — active internships in DB
      new_this_week    — active internships with created_at >= NOW() - 7 days (raw SQL)
      high_match       — user recommendations with match_percentage >= HIGH_MATCH_THRESHOLD (75)
      saved            — user applications with status = 'saved'
    """
    from app.models.application import Application
    from app.models.recommendation import Recommendation as Rec
    from app.services.recommendation_engine import HIGH_MATCH_THRESHOLD

    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    import time as _time
    _t0 = _time.perf_counter()

    # Total active internships
    total_positions = db.execute(
        text("SELECT COUNT(*) FROM internships WHERE is_active = true")
    ).scalar() or 0

    # New this week — EXACT raw SQL as specified, uses DB clock so no drift
    new_this_week = db.execute(
        text(
            "SELECT COUNT(*) FROM internships "
            "WHERE is_active = true "
            "AND created_at >= NOW() - INTERVAL '7 days'"
        )
    ).scalar() or 0

    # High match — recommendations for this user with score >= HIGH_MATCH_THRESHOLD (75).
    # Uses the canonical threshold so the counter agrees with the High/Medium/Low
    # buckets shown on the cards.
    high_match = (
        db.query(Rec)
        .filter(Rec.user_id == user.id, Rec.match_percentage >= HIGH_MATCH_THRESHOLD)
        .count()
    )

    # Saved — applications this user has in 'saved' status
    saved = (
        db.query(Application)
        .filter(Application.user_id == user.id, Application.status == "saved")
        .count()
    )

    _elapsed = round(_time.perf_counter() - _t0, 4)
    _stats_logger.info(
        "stats.computed user_id=%d total=%d new_this_week=%d high_match=%d saved=%d elapsed_s=%.4f",
        user.id, total_positions, new_this_week, high_match, saved, _elapsed,
    )

    return {
        "total_positions": total_positions,
        "new_this_week": new_this_week,
        "high_match": high_match,
        "saved": saved,
    }

@router.get("/{internship_id}", response_model=InternshipDetailResponse)
async def get_internship(internship_id: int, db: Session = Depends(get_db)):
    internship = db.query(Internship).filter(Internship.id == internship_id).first()
    if not internship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found")
    skills = db.query(InternshipSkill).filter(
        InternshipSkill.internship_id == internship_id
    ).all()
    return {
        "internship": InternshipOut.model_validate(internship),
        "required_skills": [s.skill_name for s in skills],
    }


@router.get("/{internship_id}/skill-gap", response_model=SkillGapResponse)
async def skill_gap(
    internship_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Returns matched/missing skills for this user + internship.

    Reads the STORED semantic matched/missing (cosine >= 0.70) that the
    recommendation engine computed at refresh time — no embeddings on read,
    so this view always agrees with the match score and the recommendation chips.
    Run POST /api/recommendations/refresh first to populate these.
    """
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    internship = db.query(Internship).filter(Internship.id == internship_id).first()
    if not internship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found")

    rec = (
        db.query(Recommendation)
        .filter(
            Recommendation.user_id == user.id,
            Recommendation.internship_id == internship_id,
        )
        .first()
    )

    if rec is None:
        # No recommendation scored yet for this internship+user. There is no stored
        # score to return, so ask the client to refresh rather than inventing one.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendation for this internship yet. Run /api/recommendations/refresh first.",
        )

    # Everything comes straight from the stored recommendation row — matched/missing
    # AND match_percentage. match_percentage is the composite score (0-100), the SAME
    # value /api/recommendations returns. It is NOT derived from skill counts here.
    return {
        "matched_skills": sorted(rec.matched_skills or []),
        "missing_skills": sorted(rec.missing_skills or []),
        "match_percentage": rec.match_percentage or 0.0,
    }


@router.get("/{internship_id}/skill-gap/simulations", response_model=SkillSimulationsResponse)
async def skill_gap_simulations(
    internship_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    "What if" simulation: for each missing skill, estimate the new match %
    if the user were to add that skill to their profile.

    Uses an analytical formula derived from the stored composite score components,
    so it is instant (no embeddings, no LLM). The delta is computed from the
    weighted skill-coverage, skill-depth, and domain-alignment sub-scores only
    — semantic similarity and seniority are unaffected by adding a skill.

    Formula (all weights from MatchScoringAgent.DEFAULT_WEIGHTS):
      Δ_coverage  = w_S / total_w                  (× component weight 0.25)
      Δ_depth     = w_S / total_w × 0.45           (matched_ratio sub-weight inside depth × 0.20)
      Δ_domain    = 1 / n_required × 0.40          (overlap_ratio sub-weight inside domain × 0.15)

      Δ_composite = Δ_coverage × 0.25
                  + Δ_depth    × 0.20
                  + Δ_domain   × 0.15
    """
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    internship = db.query(Internship).filter(Internship.id == internship_id).first()
    if not internship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found")

    rec = (
        db.query(Recommendation)
        .filter(
            Recommendation.user_id == user.id,
            Recommendation.internship_id == internship_id,
        )
        .first()
    )
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendation for this internship yet. Run /api/recommendations/refresh first.",
        )

    matched_skills: list[str] = rec.matched_skills or []
    missing_skills: list[str] = rec.missing_skills or []
    current_pct: float = rec.match_percentage or 0.0

    if not missing_skills:
        # Nothing to simulate
        return SkillSimulationsResponse(
            current_pct=current_pct,
            simulations=[],
        )

    # Reconstruct the required skills list and skill weights from the stored internship.
    required_db = db.query(InternshipSkill).filter(
        InternshipSkill.internship_id == internship_id
    ).all()
    required_skills: list[str] = [_normalize(s.skill_name) for s in required_db]

    if not required_skills:
        # Fallback: use stored matched + missing as required set
        required_skills = [_normalize(s) for s in matched_skills + missing_skills]

    # Re-classify skills to get per-skill weights (same logic used at score time).
    domain_map = {
        frozenset(["machine learning", "deep learning", "pytorch", "tensorflow",
                   "nlp", "computer vision", "ai", "ml"]): "ai_ml",
        frozenset(["react", "vue", "angular", "frontend", "css", "html", "next.js"]): "frontend",
        frozenset(["django", "fastapi", "flask", "node", "backend", "rest api"]): "backend",
        frozenset(["aws", "gcp", "azure", "devops", "kubernetes", "docker"]): "devops",
        frozenset(["pandas", "numpy", "sql", "data analysis", "spark", "etl"]): "data",
    }
    title_lower = _normalize(internship.title or "")
    skill_set = set(required_skills)
    domain = "general"
    best = 0
    for kws, dom in domain_map.items():
        overlap = len(kws & skill_set)
        if overlap > best:
            best, domain = overlap, dom

    classifier = SkillClassifier()
    skill_weights: dict[str, int] = classifier.classify(
        skills=required_skills,
        domain=domain,
        title=internship.title or "",
    )

    fallback_w = SKILL_WEIGHTS["important"]
    total_w = sum(skill_weights.get(s, fallback_w) for s in required_skills)
    n_required = len(required_skills)

    simulations: list[SkillSimulation] = []
    # match_percentage is now weighted skill COVERAGE × 100. Adding one skill S
    # raises matched_weight by w_s, so the displayed % rises by EXACTLY
    # (w_s / total_w) × 100. This delta is the true change in the shown number —
    # no composite reconstruction, so the simulation can never disagree with the
    # score it's projecting from.
    for skill in missing_skills:
        skill_n = _normalize(skill)
        w_s = skill_weights.get(skill_n, fallback_w)

        delta_coverage = (w_s / total_w) if total_w > 0 else 0.0

        simulated_pct = min(100.0, current_pct + delta_coverage * 100)
        delta_pct = simulated_pct - current_pct

        new_label = _derive_match_label(simulated_pct / 100)
        simulations.append(SkillSimulation(
            skill=skill,
            simulated_pct=round(simulated_pct, 1),
            delta_pct=round(delta_pct, 1),
            new_label=new_label,
        ))

    # Sort by delta descending — highest-impact skills first
    simulations.sort(key=lambda s: s.delta_pct, reverse=True)

    # Phase 0: record the what-if engagement (best-effort). Top result only —
    # it's the highest-impact skill the user was shown.
    top_sim = simulations[0] if simulations else None
    log_event(
        EVENT_WHATIF_SIMULATED,
        user_id=user.id,
        internship_id=internship_id,
        payload={
            "current_pct": current_pct,
            "n_missing": len(missing_skills),
            "top_skill": top_sim.skill if top_sim else None,
            "top_delta_pct": top_sim.delta_pct if top_sim else None,
        },
    )

    return SkillSimulationsResponse(
        current_pct=current_pct,
        simulations=simulations,
    )





@router.get("/{internship_id}/match-insights", response_model=MatchInsightsResponse)
async def match_insights(
    internship_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Role-aware, stack-aware match insights for this user + internship.

    Reads the STORED recommendation (matched/missing + weighted-coverage match %)
    and enriches it into a human-like career-guide bundle: detected role & stack,
    missing skills grouped into core/secondary/optional, weighted skill impacts,
    a "why you match" explanation, and a mentor-style recommendation.

    match_percentage is passed through verbatim from the stored recommendation —
    this endpoint never computes a second, competing score. Run
    POST /api/recommendations/refresh first to populate the recommendation.
    """
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    internship = db.query(Internship).filter(Internship.id == internship_id).first()
    if not internship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found")

    rec = (
        db.query(Recommendation)
        .filter(
            Recommendation.user_id == user.id,
            Recommendation.internship_id == internship_id,
        )
        .first()
    )
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendation for this internship yet. Run /api/recommendations/refresh first.",
        )

    # Required skills straight from the internship (already stack-filtered at
    # refresh time via _get_required_skills, but we re-read the stored rows here).
    required_db = db.query(InternshipSkill).filter(
        InternshipSkill.internship_id == internship_id
    ).all()
    required_skills = [s.skill_name for s in required_db]

    from app.services.career_match_service import build_match_insights

    insights = build_match_insights(
        title=internship.title or "",
        company=internship.company or "",
        description=internship.description or "",
        required_skills=required_skills,
        matched_skills=rec.matched_skills or [],
        missing_skills=rec.missing_skills or [],
        match_percentage=rec.match_percentage or 0.0,
        db=db,
        user_id=user.id,
        internship_id=internship_id,
    )

    # Phase 0: record that the user opened the match insights for this role.
    log_event(
        EVENT_MATCH_VIEWED,
        user_id=user.id,
        internship_id=internship_id,
        payload={
            "match_pct": rec.match_percentage or 0.0,
            "matched": len(rec.matched_skills or []),
            "missing": len(rec.missing_skills or []),
        },
    )

    return insights


@router.get("/{internship_id}/explain", response_model=ExplanationResponse)
async def explain_match(
    internship_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Grounded explanation of why this internship matches the user's profile
    (Phase 3). Lazy loaded — only called when the user explicitly requests it.

    The LLM may only write prose ABOUT the matched/missing skills already stored
    on the recommendation row. Any invented skill discards the LLM output and we
    serve a deterministic fallback. The match score is read from storage and is
    never recomputed here.
    """
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    # Fetch internship
    internship = db.query(Internship).filter(Internship.id == internship_id).first()
    if not internship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found")

    # Use the STORED semantic matched/missing from this user's recommendation row
    # (cosine >= 0.70, computed at refresh time). No exact string matching and no
    # embedding recompute on read — the chips stay consistent with the match score.
    rec = (
        db.query(Recommendation)
        .filter(
            Recommendation.user_id == user.id,
            Recommendation.internship_id == internship_id,
        )
        .first()
    )
    matched_clean = (rec.matched_skills or [])[:5] if rec else []
    missing_clean = (rec.missing_skills or [])[:5] if rec else []

    # DETERMINISTIC score — read-only passthrough.
    match_score = (rec.match_percentage or 0.0) if rec else 0.0

    explanation, source = generate_explanation(
        db=db,
        user_id=user.id,
        job=internship,
        matched_skills=matched_clean,
        missing_skills=missing_clean,
        score=match_score,
    )

    return ExplanationResponse(
        internship_id=internship_id,
        title=internship.title,
        company=internship.company,
        match_score=match_score,
        matched_skills=[s for s in matched_clean],
        missing_skills=[s for s in missing_clean],
        explanation=explanation,
        source=source,
    )
