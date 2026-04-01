from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.internship import Internship
from app.models.internship_skill import InternshipSkill
from app.models.resume import Resume
from app.models.skill import Skill
from app.models.experience import Experience
from app.models.project import Project
from app.services.auth_service import AuthService
from app.schemas.internship import (
    InternshipDetailResponse,
    InternshipListResponse,
    InternshipOut,
    MatchExplanation,
    SkillGapResponse,
)
from app.services.recommendation_engine import explain_match as generate_explanation

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

    required = db.query(InternshipSkill).filter(
        InternshipSkill.internship_id == internship_id
    ).all()
    user_skills = db.query(Skill).filter(Skill.user_id == user.id).all()

    required_set = {s.skill_name.lower() for s in required}
    user_set = {s.skill_name.lower() for s in user_skills}

    matched = sorted({s.skill_name for s in required if s.skill_name.lower() in user_set})
    missing = sorted({s.skill_name for s in required if s.skill_name.lower() not in user_set})

    match_percentage = 0.0
    if required_set:
        match_percentage = (len(matched) / len(required_set)) * 100

    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "match_percentage": round(match_percentage, 2),
    }





@router.get("/{internship_id}/explain", response_model=MatchExplanation)
async def explain_match(
    internship_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Generate a human-readable explanation of why this internship
    matches the user's profile using Groq LLM.
    Lazy loaded — only called when user explicitly requests it.
    """
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    # Fetch internship
    internship = db.query(Internship).filter(Internship.id == internship_id).first()
    if not internship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found")

    user_skills = db.query(Skill).filter(Skill.user_id == user.id).all()
    required = db.query(InternshipSkill).filter(
        InternshipSkill.internship_id == internship_id
    ).all()

    required_skills = [s.skill_name for s in required]
    matched = set([s.skill_name.lower() for s in user_skills]) & set([s.lower() for s in required_skills])
    missing = set([s.lower() for s in required_skills]) - set([s.skill_name.lower() for s in user_skills])

    matched_clean = list(matched)[:5]
    missing_clean = list(missing)[:5]

    experiences = db.query(Experience).filter(Experience.user_id == user.id).all()
    projects = db.query(Project).filter(Project.user_id == user.id).all()
    
    user_experience = "; ".join([f"{e.role} at {e.company}" for e in experiences if e.role and e.company])
    user_projects = "; ".join([p.name for p in projects if p.name])

    user_skills_str = ", ".join([s.skill_name for s in user_skills]) if user_skills else "None"

    import re
    clean_description = re.sub(r"<[^>]+>", " ", internship.description or "")
    clean_description = re.sub(r"\s+", " ", clean_description).strip()
    
    explanation = generate_explanation(
        internship_title=internship.title,
        internship_company=internship.company,
        internship_description=clean_description[:2000],
        user_skills=user_skills_str,
        matched_skills=matched_clean,
        missing_skills=missing_clean,
        user_experience=user_experience,
        user_projects=user_projects,
    )

    return explanation
