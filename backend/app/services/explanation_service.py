"""
app/services/explanation_service.py

Phase 3 — GROUNDED EXPLANATION SYSTEM.

Pipeline:   cache → LLM → validate (ground) → cache write → (on any failure) fallback

Guiding principle, identical to Phase 2 skill extraction:
    THE LLM SUGGESTS.  OUR DATA DECIDES TRUTH.

The LLM receives ONLY the deterministic inputs (matched_skills, missing_skills,
job_title, match_score) and may only write prose ABOUT those skills. After the
call, every skill it referenced is checked for membership in the input sets. One
violation — a single invented skill, or advice about a skill the user already
has — discards the whole LLM response and we serve the deterministic fallback.

Hard invariants enforced here:
  • match_score is passed through untouched. This module NEVER computes,
    adjusts, rounds, or regenerates it.
  • No LLM call ever happens on a cache hit.
  • This module is called on-demand from single-item explain endpoints ONLY.
    It must never be invoked from a recommendation LIST endpoint.
  • Never raises. Worst case is the deterministic fallback.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.explanation_cache import ExplanationCache
from app.schemas.explanation import ExplanationOutput, SkillGapAdvice, SkillReason

logger = logging.getLogger(__name__)

# Caps: keep the prompt small and the output bounded.
_MAX_MATCHED_IN_PROMPT = 8
_MAX_MISSING_IN_PROMPT = 6
_MAX_TOKENS = 700

# Source markers surfaced to the API for observability.
SOURCE_CACHE = "cache"
SOURCE_LLM = "llm"
SOURCE_FALLBACK = "fallback"


# ---------------------------------------------------------------------------
# 5. LLM PROMPT TEMPLATE
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You MUST only use provided skills. Do NOT invent new ones.\n"
    "You are a concise, practical career advisor explaining a job match to a student.\n"
    "You return ONLY a single valid JSON object — no prose, no markdown fences.\n"
    "\n"
    "HARD RULES:\n"
    "1. Every skill in matched_skill_explanations MUST be copied EXACTLY from the "
    "input matched_skills list. Never add, rename, split, or merge a skill.\n"
    "2. Every skill in missing_skill_advice MUST be copied EXACTLY from the input "
    "missing_skills list. Never put a matched skill here or vice versa.\n"
    "3. Do NOT mention any technology, tool, or framework that is not in one of "
    "those two input lists.\n"
    "4. Do NOT state, recompute, or dispute the match score. It is already final.\n"
    "5. Write like a helpful mentor. Avoid robotic filler such as "
    '"matches requirement" or "aligns with the role".\n'
    "6. Each explanation says WHY that skill is useful in THIS role, in under 20 "
    "words. Each advice is one concrete, actionable next step, under 20 words.\n"
    "7. summary is ONE sentence, under 30 words.\n"
    "8. If an input list is empty, return an empty array for its section."
)

_USER_PROMPT_TEMPLATE = """Explain this job match using ONLY the skills provided below.

Input:
{payload}

Return EXACTLY this JSON shape and nothing else:
{{"matched_skill_explanations": [{{"skill": "<from matched_skills>", "explanation": "<why it helps in this role>"}}],
  "missing_skill_advice": [{{"skill": "<from missing_skills>", "advice": "<concrete next step>"}}],
  "summary": "<one sentence>"}}

Example input:
{{"matched_skills": ["python", "sql"], "missing_skills": ["docker"], "job_title": "Data Intern", "match_score": 72.0}}
Example output:
{{"matched_skill_explanations": [{{"skill": "python", "explanation": "Python drives the data cleaning and analysis scripts this team runs daily"}}, {{"skill": "sql", "explanation": "You can query the warehouse directly instead of waiting on an analyst"}}], "missing_skill_advice": [{{"skill": "docker", "advice": "Containerize one of your existing Python projects and run it locally"}}], "summary": "Your Python and SQL foundation covers the core of this role, with Docker as the main gap."}}"""


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _norm(value: Any) -> str:
    """Canonical comparison form for a skill string."""
    return str(value).strip().lower() if value is not None else ""


def _clean_skill_list(skills: Optional[Iterable[Any]]) -> list[str]:
    """Normalize + dedupe a skill list while preserving input order."""
    out: list[str] = []
    seen: set[str] = set()
    for s in skills or []:
        n = _norm(s)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


# ---------------------------------------------------------------------------
# 6a. FALLBACK — deterministic, always valid, always grounded by construction
# ---------------------------------------------------------------------------

def build_fallback(matched_skills: list[str], missing_skills: list[str]) -> ExplanationOutput:
    """
    Safe deterministic response. Grounded by construction: it only ever echoes
    skills from the input lists, so it cannot fail validation.
    """
    return ExplanationOutput(
        matched_skill_explanations=[
            SkillReason(skill=s, explanation=f"You have experience in {s}")
            for s in matched_skills
        ],
        missing_skill_advice=[
            SkillGapAdvice(skill=s, advice=f"Consider learning {s}")
            for s in missing_skills
        ],
        summary="This job matches based on your current skills.",
    )


# ---------------------------------------------------------------------------
# 6b. VALIDATION — the grounding gate
# ---------------------------------------------------------------------------

def validate_explanation(
    raw: str,
    *,
    matched_skills: list[str],
    missing_skills: list[str],
) -> tuple[bool, Optional[ExplanationOutput], str]:
    """
    Parse, shape-validate, then GROUND the LLM response.

    Returns (ok, output, reason). ok is False → caller MUST use the fallback.

    Grounding rule (mandatory, no exceptions):
      • every skill in matched_skill_explanations ∈ matched_skills
      • every skill in missing_skill_advice        ∈ missing_skills
    ANY violation fails the whole response. We do not silently drop the
    offending item: a model that invented one skill has demonstrated it is not
    respecting the constraint, so the entire output is untrustworthy.
    """
    if not raw or not isinstance(raw, str):
        return False, None, "empty_response"

    cleaned = raw.strip()

    # Strip markdown fences if the model added them despite instructions.
    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = max(parts, key=len).strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    # Isolate the outermost JSON object.
    start, end = cleaned.find("{"), cleaned.rfind("}") + 1
    if start == -1 or end <= start:
        return False, None, "no_json_object"

    try:
        data = json.loads(cleaned[start:end])
    except (ValueError, TypeError):
        return False, None, "json_parse_error"

    if not isinstance(data, dict):
        return False, None, "not_a_dict"

    # --- shape validation via pydantic ---
    try:
        output = ExplanationOutput(**data)
    except Exception as exc:  # pydantic ValidationError and friends
        logger.warning("explanation_service.shape_invalid error=%s", exc)
        return False, None, "shape_invalid"

    # --- grounding validation ---
    matched_set = set(matched_skills)
    missing_set = set(missing_skills)

    for item in output.matched_skill_explanations:
        if item.skill not in matched_set:
            return False, None, f"ungrounded_matched_skill:{item.skill}"
        if not item.explanation:
            return False, None, f"empty_explanation:{item.skill}"

    for item in output.missing_skill_advice:
        if item.skill not in missing_set:
            return False, None, f"ungrounded_missing_skill:{item.skill}"
        if not item.advice:
            return False, None, f"empty_advice:{item.skill}"

    if not output.summary:
        return False, None, "empty_summary"

    # Dedupe by skill, preserving the model's ordering.
    output.matched_skill_explanations = _dedupe_by_skill(output.matched_skill_explanations)
    output.missing_skill_advice = _dedupe_by_skill(output.missing_skill_advice)

    return True, output, "ok"


def _dedupe_by_skill(items: list) -> list:
    seen: set[str] = set()
    out = []
    for item in items:
        if item.skill not in seen:
            seen.add(item.skill)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# Groq client (lazy, module-level singleton) — mirrors Phase 2's pattern
# ---------------------------------------------------------------------------

_groq_client = None


def _get_client():
    """Lazy-init a Groq client. Returns None if unavailable (→ triggers fallback)."""
    global _groq_client
    if _groq_client is not None:
        return _groq_client
    if not getattr(settings, "GROQ_API_KEY", None):
        return None
    try:
        from groq import Groq
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    except Exception as exc:  # noqa: BLE001
        logger.warning("explanation_service.groq_init_failed error=%s", exc)
        return None
    return _groq_client


def _call_llm(
    *,
    matched_skills: list[str],
    missing_skills: list[str],
    job_title: str,
    match_score: float,
) -> Optional[str]:
    """One Groq chat call. Returns raw content str, or None on any failure."""
    client = _get_client()
    if client is None:
        return None

    payload = json.dumps(
        {
            "matched_skills": matched_skills[:_MAX_MATCHED_IN_PROMPT],
            "missing_skills": missing_skills[:_MAX_MISSING_IN_PROMPT],
            "job_title": job_title,
            "match_score": match_score,
        },
        ensure_ascii=False,
    )

    try:
        response = client.chat.completions.create(
            model=getattr(settings, "LLM_EXPLANATION_MODEL", "llama-3.1-8b-instant"),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(payload=payload)},
            ],
            temperature=0.0,  # deterministic structured output
            max_tokens=_MAX_TOKENS,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("explanation_service.llm_call_failed error=%s", exc)
        return None


# ---------------------------------------------------------------------------
# Cache layer
# ---------------------------------------------------------------------------

def _cache_get(
    db: Session, user_id: str, job_id: str, resume_version: str
) -> Optional[ExplanationOutput]:
    """Read a cached explanation. Returns None on miss or unparseable row."""
    try:
        row = (
            db.query(ExplanationCache)
            .filter(
                ExplanationCache.user_id == user_id,
                ExplanationCache.job_id == job_id,
                ExplanationCache.resume_version == resume_version,
            )
            .first()
        )
    except Exception as exc:  # noqa: BLE001  (missing table / DB hiccup)
        logger.warning("explanation_service.cache_read_failed error=%s", exc)
        return None

    if row is None or not row.explanation_json:
        return None

    try:
        return ExplanationOutput(**row.explanation_json)
    except Exception as exc:  # noqa: BLE001  (stale/incompatible cached shape)
        logger.warning("explanation_service.cache_shape_invalid error=%s", exc)
        return None


def _cache_put(
    db: Session,
    user_id: str,
    job_id: str,
    resume_version: str,
    output: ExplanationOutput,
) -> None:
    """
    Write-through after successful validation. Best-effort: a cache write
    failure must never fail the request, so we roll back and move on.
    """
    try:
        existing = (
            db.query(ExplanationCache)
            .filter(
                ExplanationCache.user_id == user_id,
                ExplanationCache.job_id == job_id,
                ExplanationCache.resume_version == resume_version,
            )
            .first()
        )
        if existing:
            existing.explanation_json = output.model_dump()
        else:
            db.add(
                ExplanationCache(
                    user_id=user_id,
                    job_id=job_id,
                    resume_version=resume_version,
                    explanation_json=output.model_dump(),
                )
            )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("explanation_service.cache_write_failed error=%s", exc)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass


def resolve_resume_version(db: Session, user_id: int) -> str:
    """
    The cache-invalidation key. Latest resume version number for this user, or
    "v0" when they have none. When the user edits their resume, this changes,
    which retires every cached explanation built from the old skill set.
    """
    try:
        from app.models.resume_version import ResumeVersion

        latest = (
            db.query(ResumeVersion.version_number)
            .filter(ResumeVersion.user_id == user_id)
            .order_by(ResumeVersion.version_number.desc())
            .first()
        )
        if latest and latest[0] is not None:
            return f"v{latest[0]}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("explanation_service.resume_version_failed error=%s", exc)
    return "v0"


# ---------------------------------------------------------------------------
# Public service function
# ---------------------------------------------------------------------------

def generate_explanation(
    db: Session,
    user_id: Any,
    job: Any,
    matched_skills: Optional[Iterable[Any]],
    missing_skills: Optional[Iterable[Any]],
    score: float,
    *,
    resume_version: Optional[str] = None,
) -> tuple[ExplanationOutput, str]:
    """
    Produce a grounded explanation for one (user, job) pair.

    Flow (exactly as specified):
      1. check cache
      2. if hit  → return it (NO LLM call)
      3. call LLM
      4. validate (shape + grounding)
      5. if valid → cache + return
      6. else     → deterministic fallback

    `score` is accepted only to give the LLM context. It is returned to the
    caller unchanged and is NEVER recomputed here.

    Returns (ExplanationOutput, source) where source ∈ {"cache","llm","fallback"}.
    Never raises.
    """
    matched = _clean_skill_list(matched_skills)
    missing = _clean_skill_list(missing_skills)

    job_id = str(getattr(job, "id", "") or "")
    job_title = str(getattr(job, "title", "") or "")
    uid = str(user_id)

    # Nothing to explain → deterministic, no LLM call, no cache entry.
    if not matched and not missing:
        return build_fallback(matched, missing), SOURCE_FALLBACK

    version = resume_version or resolve_resume_version(db, user_id)

    # --- 1/2. cache ---
    cached = _cache_get(db, uid, job_id, version)
    if cached is not None:
        return cached, SOURCE_CACHE

    # Kill-switch → skip the call entirely.
    if not getattr(settings, "LLM_EXPLANATION_ENABLED", True):
        return build_fallback(matched, missing), SOURCE_FALLBACK

    # --- 3. LLM ---
    raw = _call_llm(
        matched_skills=matched,
        missing_skills=missing,
        job_title=job_title,
        match_score=float(score),
    )
    if raw is None:
        return build_fallback(matched, missing), SOURCE_FALLBACK

    # --- 4. validate ---
    ok, output, reason = validate_explanation(
        raw, matched_skills=matched, missing_skills=missing
    )
    if not ok or output is None:
        logger.info("explanation_service.fallback reason=%s job_id=%s", reason, job_id)
        return build_fallback(matched, missing), SOURCE_FALLBACK

    # --- 5. cache + return ---
    _cache_put(db, uid, job_id, version, output)
    return output, SOURCE_LLM
