"""
Career match insights service.

Turns a stored recommendation (matched/missing skills + composite match %) into
a ROLE-AWARE, STACK-AWARE, human-like insight bundle:

    role_type, stack_type, match_percentage,
    matched_skills, missing_skills{core, secondary, optional},
    explanation, recommendation, top_missing_skill,
    skill_impacts[{skill, impact}]

Design:
  • match_percentage is passed through VERBATIM from the stored recommendation.
    We do NOT invent a second, competing score — the composite score remains the
    single source of truth everywhere (card, skill-gap, insights).
  • Skill categories reuse SkillClassifier (core=5 / secondary=3 / optional=1),
    the same weighting used at score time.
  • skill_impacts reuse the SAME analytical delta formula as the what-if
    simulations endpoint, so "REST API → +8%" here matches the simulation there.
  • explanation + match_reasons come from the Phase 3 grounded explanation
    service (validated + cached, so it can only name real matched/missing
    skills, and falls back to a deterministic template on any failure).
  • recommendation is still a deterministic template (no LLM cost).

Pure-ish: only depends on role_stack + recommendation_engine constants. Never
raises on bad input — returns a safe, fully-populated dict.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.services.role_stack import detect_role, detect_stack
from app.services.recommendation_engine import (
    ALL_MATCHED_THRESHOLD,
    SKILL_WEIGHTS,
    SkillClassifier,
    _normalize,
)

# ---------------------------------------------------------------------------
# role_type -> SkillClassifier domain (so core-skill detection is role-aware)
# ---------------------------------------------------------------------------

_ROLE_TO_DOMAIN: Dict[str, str] = {
    "ML_ROLE":       "ai_ml",
    "DATA_ROLE":     "data",
    "FRONTEND_ROLE": "frontend",
    "MOBILE_ROLE":   "mobile",
    "DEVOPS_ROLE":   "devops",
    "SECURITY_ROLE": "security",
    "BACKEND_ROLE":  "backend",
    "FULLSTACK_ROLE": "backend",
    "GENERAL_ROLE":  "general",
}

# The "path" the recommendation nudges the user to continue on — always
# role-consistent (a Data role is never told to continue on a "Go Backend"
# path). Backend-family roles override this with their detected language stack
# when one is known (e.g. "with Python Backend").
_ROLE_PATH: Dict[str, str] = {
    "ML_ROLE":        "building in Machine Learning",
    "DATA_ROLE":      "building in Data Science",
    "FRONTEND_ROLE":  "growing as a Frontend developer",
    "MOBILE_ROLE":    "building Mobile apps",
    "DEVOPS_ROLE":    "building in DevOps / Cloud",
    "SECURITY_ROLE":  "building in Security",
    "BACKEND_ROLE":   "with backend development",
    "FULLSTACK_ROLE": "with full-stack development",
    "GENERAL_ROLE":   "on your software engineering path",
}

# Backend-family roles whose recommendation path should name the language stack.
_LANGUAGE_STACK_ROLES = {"BACKEND_ROLE", "FULLSTACK_ROLE", "GENERAL_ROLE"}

# MatchScoringAgent component weights — kept in sync with
# routes/internships.py::skill_gap_simulations so impacts agree across surfaces.
# match_percentage is now weighted skill COVERAGE × 100, so the impact of adding
# one skill is simply its share of the total required weight.
_W_COVERAGE = 1.0


def _grounded_explanation(
    *,
    db: Any,
    user_id: Any,
    internship_id: Any,
    title: str,
    matched_skills: List[str],
    missing_skills: List[str],
    match_percentage: float,
):
    """
    Fetch the grounded explanation for this match. Returns
    (ExplanationOutput, source).

    Imported lazily to keep this module importable without a DB session, and to
    avoid a circular import at module load. With no db/user_id/internship_id we
    go straight to the service's deterministic fallback — no LLM call, no cache
    lookup — so callers that only want the numeric insight bundle pay nothing.
    """
    from app.services.explanation_service import build_fallback, generate_explanation

    if db is None or user_id is None or internship_id is None:
        return build_fallback(matched_skills, missing_skills), "fallback"

    class _Job:
        id = internship_id

    _Job.title = title

    try:
        return generate_explanation(
            db=db,
            user_id=user_id,
            job=_Job(),
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            score=match_percentage,
        )
    except Exception:  # noqa: BLE001 — this module must never raise
        return build_fallback(matched_skills, missing_skills), "fallback"


def _weighted_impact(
    w_s: int, total_w: int, n_required: int
) -> float:
    """
    Projected match-% gain from adding one skill, in percentage points.

    match_percentage = (matched_weight / total_weight) × 100. Adding a skill of
    weight w_s raises matched_weight by w_s, so the gain is EXACTLY:
        Δ = (w_s / total_w) × 100

    This is the same delta the what-if simulation reports, so "REST API → +8%"
    here matches the simulation there. n_required is accepted for signature
    stability but no longer needed.
    """
    if total_w > 0:
        return round((w_s / total_w) * 100, 1)
    return 0.0


def _titlecase_skill(skill: str) -> str:
    """Human-friendly casing: 'rest api' -> 'REST API', 'fastapi' -> 'FastAPI'."""
    special = {
        "rest api": "REST API", "api": "API", "sql": "SQL", "aws": "AWS",
        "gcp": "GCP", "css": "CSS", "html": "HTML", "ci/cd": "CI/CD",
        "fastapi": "FastAPI", "nodejs": "Node.js", "node.js": "Node.js",
        "nlp": "NLP", "ml": "ML", "graphql": "GraphQL", "ui": "UI", "ux": "UX",
    }
    s = _normalize(skill)
    if s in special:
        return special[s]
    return skill.strip().title() if skill else skill


def _join_human(items: List[str]) -> str:
    """['a','b','c'] -> 'a, b and c'."""
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])} and {items[-1]}"


def build_match_insights(
    *,
    title: str,
    company: str,
    description: str,
    required_skills: List[str],
    matched_skills: List[str],
    missing_skills: List[str],
    match_percentage: float,
    db: Any = None,
    user_id: Any = None,
    internship_id: Any = None,
) -> Dict[str, Any]:
    """
    Assemble the full role-aware insight bundle. Never raises.

    `explanation` and `match_reasons` come from the Phase 3 grounded
    explanation service when a db session + ids are supplied; that path is
    cached and validated so it can only reference real matched/missing skills.
    Without a session (or on any failure) the service's own deterministic
    fallback supplies them, so this function still never raises.
    """
    title = title or ""
    matched_skills = [_normalize(s) for s in (matched_skills or []) if s]
    missing_skills = [_normalize(s) for s in (missing_skills or []) if s]
    required_skills = [_normalize(s) for s in (required_skills or []) if s]

    # Required set should at minimum cover matched+missing (in case the caller
    # passed a thin required list).
    if not required_skills:
        required_skills = list(dict.fromkeys(matched_skills + missing_skills))

    # --- Role + stack detection ------------------------------------------------
    role_type, role_label = detect_role(title, description, required_skills)
    # Stack is ROLE-GATED: pass role_type so a Data role can never resolve to a
    # backend language stack ("Go Backend" etc). See role_stack.detect_stack.
    stack_type, stack_label = detect_stack(
        title, description, required_skills, role_type=role_type
    )
    domain = _ROLE_TO_DOMAIN.get(role_type, "general")

    # --- Classify skills into weights (core/secondary/optional) ----------------
    classifier = SkillClassifier()
    weights = classifier.classify(skills=required_skills, domain=domain, title=title)
    fallback_w = SKILL_WEIGHTS["important"]

    total_w = sum(weights.get(s, fallback_w) for s in required_skills)
    n_required = len(required_skills)

    core_missing: List[str] = []
    secondary_missing: List[str] = []
    optional_missing: List[str] = []
    # Item #10: sort missing skills within each category by impact (highest boost
    # first), so the top core skill to learn leads its group. Impact is monotonic
    # in weight, so sorting by weight desc == sorting by boost desc.
    missing_sorted = sorted(
        missing_skills,
        key=lambda s: weights.get(s, fallback_w),
        reverse=True,
    )
    for s in missing_sorted:
        w = weights.get(s, fallback_w)
        label = _titlecase_skill(s)
        if w >= SKILL_WEIGHTS["core"]:
            core_missing.append(label)
        elif w >= SKILL_WEIGHTS["important"]:
            secondary_missing.append(label)
        else:
            optional_missing.append(label)

    # --- Weighted skill impacts (sorted highest first) -------------------------
    impacts = [
        {
            "skill": _titlecase_skill(s),
            "impact": _weighted_impact(weights.get(s, fallback_w), total_w, n_required),
        }
        for s in missing_skills
    ]
    impacts.sort(key=lambda d: d["impact"], reverse=True)

    top_missing_skill = impacts[0]["skill"] if impacts else ""

    # --- Grounded explanation ("why you match") --------------------------------
    # Delegated to the Phase 3 explanation service. That layer is validated:
    # every skill it names must be a member of matched_skills / missing_skills,
    # or its output is discarded in favour of a deterministic fallback. So this
    # still never names a skill the user doesn't have.
    matched_labels = [_titlecase_skill(s) for s in matched_skills]

    grounded, _source = _grounded_explanation(
        db=db,
        user_id=user_id,
        internship_id=internship_id,
        title=title,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        match_percentage=match_percentage,
    )

    # One bullet PER real matched skill, straight from the grounded output.
    # The service returns a self-contained sentence per skill, so we emit it
    # as-is rather than prefixing the label (which would read "Python You have
    # experience in python."). Only the trailing period is normalized.
    match_reasons: List[str] = [
        item.explanation if item.explanation.endswith((".", "!", "?"))
        else f"{item.explanation}."
        for item in grounded.matched_skill_explanations
        if item.explanation
    ]

    explanation = grounded.summary

    # --- Mentor-style recommendation ------------------------------------------
    # Depends on role_type + matched_skills. The "path" it nudges toward is
    # always role-consistent — a Data role is never told to continue on a
    # backend-language path. Backend-family roles name their language stack when
    # one was detected.
    if role_type in _LANGUAGE_STACK_ROLES and stack_label:
        path = f"with {stack_label}"
    else:
        path = _ROLE_PATH.get(role_type, "on your current path")

    focus = _join_human((core_missing or secondary_missing or optional_missing)[:2])

    # Item #11: anchor on the STRONGEST matched skills (highest weight), not just
    # the first one listed — "Since you already have Python and SQL..." rather
    # than "Since you have Git...".
    strong_matched = sorted(
        matched_skills,
        key=lambda s: weights.get(s, fallback_w),
        reverse=True,
    )
    strong_labels = [_titlecase_skill(s) for s in strong_matched]
    anchor = _join_human(strong_labels[:2])

    pct = float(match_percentage or 0.0)

    if not matched_labels:
        # Item #15: no matched skills — never fake a strength.
        if focus:
            recommendation = (
                f"No strong skill match yet — to break into this {role_label} role, "
                f"start by {path}. Begin with {focus}; those move your match the most."
            )
        else:
            recommendation = (
                f"No strong skill match yet — start by {path} and build the core "
                f"skills for this {role_label} role."
            )
    elif not focus:
        # Item #15: matched skills, nothing left to build.
        if pct >= ALL_MATCHED_THRESHOLD:
            recommendation = (
                f"Strong match — your experience with {anchor} covers what this "
                f"{role_label} role needs. Polish your projects and apply with confidence."
            )
        else:
            recommendation = (
                f"Since you already have experience with {anchor}, continue {path}. "
                f"You cover the key skills here — strengthen your projects and apply."
            )
    else:
        recommendation = (
            f"Since you already have experience with {anchor}, continue {path}. "
            f"Focusing on {focus} next will improve your match for this role."
        )

    return {
        "role_type": role_type,
        "role_label": role_label,
        "stack_type": stack_type,
        "stack_label": stack_label,
        "match_percentage": round(pct, 1),
        "matched_skills": matched_labels,
        "missing_skills": {
            "core": core_missing,
            "secondary": secondary_missing,
            "optional": optional_missing,
        },
        "explanation": explanation,
        "match_reasons": match_reasons,
        "recommendation": recommendation,
        "top_missing_skill": top_missing_skill,
        "skill_impacts": impacts,
    }
