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
  • explanation + recommendation are deterministic templates (no extra LLM cost,
    no hallucinated skills) but read like a mentor, not a keyword dump.

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

# Short, role-specific phrase describing the KIND OF WORK the role involves.
# Used to explain WHY the user's matched skills matter — described as TASKS,
# never as named technologies, so the explanation can never imply the user has
# a skill they don't. (Explanations reference matched_skills only; this phrase
# is role context, not a skill claim.)
_ROLE_CONTEXT: Dict[str, str] = {
    "ML_ROLE":        "model building and experimentation tasks",
    "DATA_ROLE":      "data processing and analysis tasks",
    "FRONTEND_ROLE":  "building responsive, user-facing interfaces",
    "MOBILE_ROLE":    "building and shipping mobile apps",
    "DEVOPS_ROLE":    "automation and cloud infrastructure work",
    "SECURITY_ROLE":  "securing systems and analysing threats",
    "BACKEND_ROLE":   "server-side and API development work",
    "FULLSTACK_ROLE": "end-to-end web development work",
    "GENERAL_ROLE":   "the core engineering work",
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

# Role -> how a matched skill is FRAMED as helping. One clause per role, used to
# build per-skill "why you match" bullets that are domain-specific (item #7) and
# non-generic (item #6/#14). The clause completes: "<Skill> {clause}".
# Phrased as tasks/outcomes, never inventing a second skill.
_ROLE_SKILL_HELP: Dict[str, str] = {
    "ML_ROLE":        "supports the model-building and experimentation work in this role",
    "DATA_ROLE":      "is used directly for the data processing, analysis and modeling in this role",
    "FRONTEND_ROLE":  "helps you build the responsive, user-facing interfaces this role needs",
    "MOBILE_ROLE":    "applies to building and shipping the mobile features this role owns",
    "DEVOPS_ROLE":    "feeds into the automation and cloud-infrastructure work here",
    "SECURITY_ROLE":  "applies to securing systems and analysing threats in this role",
    "BACKEND_ROLE":   "applies to the server logic, APIs and database handling this role owns",
    "FULLSTACK_ROLE": "applies across the end-to-end web development this role covers",
    "GENERAL_ROLE":   "is directly useful for the core engineering work in this role",
}

# A few well-known skills get a MORE specific clause than the role default, so a
# bullet reads like a mentor, not a template. Keyed by normalized skill name.
# Still references ONLY the matched skill — the clause never names another skill.
_SKILL_SPECIFIC_HELP: Dict[str, str] = {
    "python":     "is the primary language for this role's day-to-day work",
    "sql":        "lets you query and shape the data this role depends on",
    "pandas":     "is used to clean, transform and explore datasets here",
    "numpy":      "underpins the numerical work this role involves",
    "react":      "is the framework you'd build this role's UI in",
    "docker":     "is how this role packages and ships services",
    "aws":        "covers the cloud environment this role deploys to",
    "git":        "keeps your work reviewable in this role's collaboration flow",
    "rest api":   "is how this role's services talk to each other",
    "tensorflow": "is a core framework for this role's model work",
    "pytorch":    "is a core framework for this role's model work",
}

# MatchScoringAgent component weights — kept in sync with
# routes/internships.py::skill_gap_simulations so impacts agree across surfaces.
# match_percentage is now weighted skill COVERAGE × 100, so the impact of adding
# one skill is simply its share of the total required weight.
_W_COVERAGE = 1.0


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
) -> Dict[str, Any]:
    """
    Assemble the full role-aware insight bundle. Never raises.
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

    # --- Human-like explanation ("why you match") -----------------------------
    # STRICT: everything here references ONLY the user's actual matched_skills.
    # We never name a skill the user doesn't have.
    #
    # match_reasons: one bullet PER real matched skill (item #14) — each explains
    # HOW that specific skill helps in THIS role (role-aware, item #6/#7), using a
    # skill-specific clause when we have one, else the role default.
    matched_labels = [_titlecase_skill(s) for s in matched_skills]
    role_context = _ROLE_CONTEXT.get(role_type, "the core requirements of this role")
    role_help = _ROLE_SKILL_HELP.get(role_type, "is relevant to the core work in this role")

    match_reasons: List[str] = []
    for raw, label in zip(matched_skills, matched_labels):
        clause = _SKILL_SPECIFIC_HELP.get(raw, role_help)
        match_reasons.append(f"{label} {clause}.")

    if matched_labels:
        top_matched = _join_human(matched_labels[:3])
        verb = "helps" if len(matched_labels[:3]) == 1 else "help"
        explanation = (
            f"You match this {role_label} role because your experience with "
            f"{top_matched} {verb} with the {role_context} required for this position."
        )
    else:
        explanation = (
            f"This {role_label} role centers on {role_context}. Your profile "
            f"doesn't show those skills yet, so building them is the fastest way in."
        )

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
