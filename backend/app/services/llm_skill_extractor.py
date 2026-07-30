"""
app/services/llm_skill_extractor.py

Phase 2 — LLM-first skill extraction (the PRIMARY path).

Pipeline:   LLM  →  validate  →  ground  →  (on any failure) fallback

Guiding principle:  THE LLM SUGGESTS.  THE TAXONOMY DECIDES TRUTH.
  • The LLM is used to maximize RECALL — it proposes skills the keyword layer
    misses, and classifies the role.
  • Every proposed skill is GROUNDED via skill_taxonomy.normalize_skill(): if it
    does not resolve to a known canonical skill, it is DROPPED. No fuzzy match,
    no exceptions. This is what keeps precision high while recall rises.
  • Any failure (no key / kill-switch / timeout / bad JSON / validation fail)
    falls back to the existing keyword SkillExtractor. Worst case == today's
    baseline; the LLM is pure upside.

Public surface mirrors the legacy extractor so downstream callers are unchanged:
  LLMSkillExtractor.extract(text, title)        -> {"skills": [...], "role_type": "..."}
  LLMSkillExtractor.extract_skills(text, title) -> [...]   (skills only)

Output contract (STRICT, never violated even on fallback):
  {"skills": list[str], "role_type": "data"|"backend"|"frontend"|"general"}
`skills` are lowercase canonical names — identical shape to the old path, so
scoring / match% / downstream logic are untouched.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.config import settings
from app.services.role_stack import detect_role
from app.services.skill_extractor import SkillExtractor  # keyword fallback
from app.services.skill_taxonomy import normalize_skill

logger = logging.getLogger(__name__)

# The ONLY role_type values allowed on the output.
ALLOWED_ROLE_TYPES = {"data", "backend", "frontend", "general"}

# Collapse role_stack.detect_role()'s fine-grained roles into the 4 buckets.
_ROLE_BUCKET: dict[str, str] = {
    "ML_ROLE": "data",
    "DATA_ROLE": "data",
    "FRONTEND_ROLE": "frontend",
    "MOBILE_ROLE": "frontend",     # client-side work
    "DEVOPS_ROLE": "backend",
    "SECURITY_ROLE": "backend",
    "FULLSTACK_ROLE": "backend",
    "BACKEND_ROLE": "backend",
    "GENERAL_ROLE": "general",
}

_MAX_SKILLS = 25          # cap defends against a runaway model dump
_DESC_CHAR_LIMIT = 1500   # internship JDs are short; caps tokens/latency/cost

_SYSTEM_PROMPT = (
    "You extract technical skills from internship/job postings. You return ONLY a "
    "single JSON object, no prose, no markdown fences. You never invent skills "
    "that are not clearly stated or directly implied by the text."
)

_USER_PROMPT_TEMPLATE = """From the job posting below, extract every technical skill it requires or mentions and classify the role.

Return EXACTLY this JSON shape and nothing else:
{{"skills": ["<skill>", ...], "role_type": "data" | "backend" | "frontend" | "general"}}

Rules:
- Extract TWO categories of skills:
  1. TOOLS: programming languages, frameworks, libraries, databases, cloud services, platforms (e.g. "python", "react", "docker", "aws", "postgresql")
  2. CONCEPTS: technical disciplines, methodologies, and domain areas (e.g. "machine learning", "deep learning", "computer vision", "nlp", "data visualization", "ci/cd", "etl", "statistics", "rest api")
  Both categories are equally important. Do NOT skip concepts just because they are not tool names.
- Include a skill if it is explicitly mentioned OR directly implied (e.g. "Django REST Framework" implies "python", "rest api", AND "django"; "fine-tune transformers" implies "deep learning" and "nlp").
- Include multi-word skills as-is: "machine learning", "computer vision", "react native", "spring boot", "deep learning". Do NOT split them into individual words.
- Do NOT include: soft skills, company names, job perks, degrees, architecture patterns (e.g. "MVVM", "microservices"), or generic terms ("motivated", "fast-paced").
- Normalize to canonical lowercase: "JS"->"javascript", "Node"->"nodejs", "postgres"->"postgresql", "k8s"->"kubernetes", "ML"->"machine learning", "DL"->"deep learning", "CV"->"computer vision", "CI/CD"->"ci/cd".
- role_type: "data" (data science/ML/analytics), "backend" (server/APIs/infra), "frontend" (UI/web/mobile clients), else "general".
- If the posting has no real technical content, return {{"skills": [], "role_type": "general"}}.

Example 1:
Title: "ML Engineer Intern"
Text: "Work on deep learning for computer vision. PyTorch, Python, numpy."
Output: {{"skills": ["computer vision", "deep learning", "numpy", "python", "pytorch"], "role_type": "data"}}

Example 2:
Title: "Admin Intern"
Text: "Help with scheduling and office tasks."
Output: {{"skills": [], "role_type": "general"}}

Job title: {title}
Job posting:
{description}"""


# ---------------------------------------------------------------------------
# Role helper
# ---------------------------------------------------------------------------

def _role_from_detect(text: str, title: str) -> str:
    """Bucketed role from the existing detector. Always returns an allowed value."""
    role_type, _label = detect_role(title=title, description=text)
    return _ROLE_BUCKET.get(role_type, "general")


# ---------------------------------------------------------------------------
# Step 3+4: validation + grounding
# ---------------------------------------------------------------------------

def validate_and_ground(raw: str, *, text: str, title: str) -> tuple[bool, dict, str]:
    """
    Parse, validate the SHAPE, then GROUND every skill against the taxonomy.

    Returns (ok, {"skills", "role_type"}, reason).
      ok == False  → caller must use the keyword fallback.
      ok == True   → dict is safe to return (skills grounded, role_type allowed).

    Note: an empty skills list is VALID (thin postings legitimately have none);
    only structural problems (unparseable / wrong types / missing keys) fail.
    """
    if not raw or not isinstance(raw, str):
        return False, {}, "empty_response"

    cleaned = raw.strip()

    # Strip markdown fences if the model added them despite instructions.
    if "```" in cleaned:
        parts = cleaned.split("```")
        # take the largest fenced chunk
        cleaned = max(parts, key=len).strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    # Isolate the outermost JSON object.
    start, end = cleaned.find("{"), cleaned.rfind("}") + 1
    if start == -1 or end <= start:
        return False, {}, "no_json_object"

    try:
        data = json.loads(cleaned[start:end])
    except (ValueError, TypeError):
        return False, {}, "json_parse_error"

    # --- Step 3: shape validation ---
    if not isinstance(data, dict):
        return False, {}, "not_a_dict"
    if "skills" not in data or "role_type" not in data:
        return False, {}, "missing_keys"
    if not isinstance(data["skills"], list):
        return False, {}, "skills_not_list"
    if not isinstance(data["role_type"], str):
        return False, {}, "role_type_not_str"

    # --- Step 4: grounding (anti-hallucination) ---
    grounded: list[str] = []
    seen: set[str] = set()
    for item in data["skills"]:
        if not isinstance(item, str):
            continue
        candidate = item.strip()
        # cheap sanity guards before taxonomy lookup
        if not candidate or len(candidate) > 40 or "\n" in candidate or "http" in candidate.lower():
            continue
        canonical = normalize_skill(candidate)   # None => not in taxonomy => DROP
        if canonical and canonical not in seen:
            seen.add(canonical)
            grounded.append(canonical)
        if len(grounded) >= _MAX_SKILLS:
            break

    grounded.sort()

    # --- Step 5: role_type must be one of the 4 allowed; else fall back to detect_role ---
    role_type = data["role_type"].strip().lower()
    if role_type not in ALLOWED_ROLE_TYPES:
        role_type = _role_from_detect(text, title)

    return True, {"skills": grounded, "role_type": role_type}, "ok"


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def _keyword_fallback(text: str, title: str) -> dict:
    """
    The safety net: today's keyword extractor (0.97/0.64 baseline) for skills,
    detect_role() for role_type. Also grounds the keyword output so the contract
    (canonical, deduped) is identical to the LLM path.
    """
    combined = f"{title} {text}".strip()
    raw_skills = SkillExtractor.extract_skills(combined)
    grounded: list[str] = []
    seen: set[str] = set()
    for s in raw_skills:
        canonical = normalize_skill(s) or (s.strip().lower() if s and s.strip() else None)
        if canonical and canonical not in seen:
            seen.add(canonical)
            grounded.append(canonical)
    grounded.sort()
    return {"skills": grounded, "role_type": _role_from_detect(text, title)}


# ---------------------------------------------------------------------------
# Groq client (lazy, module-level singleton)
# ---------------------------------------------------------------------------

_groq_client = None


def _get_client():
    """Lazy-init a Groq client. Returns None if unavailable (→ triggers fallback)."""
    global _groq_client
    if _groq_client is not None:
        return _groq_client
    if not settings.GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm_skill_extractor.groq_init_failed error=%s", exc)
        return None
    return _groq_client


def _call_llm(text: str, title: str) -> Optional[str]:
    """One Groq chat call. Returns raw content str, or None on any failure."""
    client = _get_client()
    if client is None:
        return None

    prompt = _USER_PROMPT_TEMPLATE.format(
        title=(title or "").strip(),
        description=(text or "")[:_DESC_CHAR_LIMIT].strip(),
    )
    try:
        response = client.chat.completions.create(
            model=getattr(settings, "LLM_EXTRACTION_MODEL", "llama-3.1-8b-instant"),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,          # deterministic structured output
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm_skill_extractor.llm_call_failed error=%s", exc)
        return None


# ---------------------------------------------------------------------------
# Public extractor
# ---------------------------------------------------------------------------

class LLMSkillExtractor:
    """LLM-first extractor with taxonomy grounding + keyword fallback."""

    @staticmethod
    def extract(text: str, title: str = "") -> dict:
        """
        Primary entry point. ALWAYS returns
            {"skills": list[str], "role_type": "data|backend|frontend|general"}
        Never raises.
        """
        # Empty input: skip the call entirely (protects thin_clean_rate + quota).
        if not (text or title):
            return {"skills": [], "role_type": "general"}

        # Kill-switch / no key → deterministic fallback.
        if not getattr(settings, "LLM_SKILL_EXTRACTION_ENABLED", True):
            return _keyword_fallback(text, title)

        raw = _call_llm(text, title)
        if raw is None:
            return _keyword_fallback(text, title)

        ok, result, reason = validate_and_ground(raw, text=text, title=title)
        if not ok:
            logger.info("llm_skill_extractor.fallback reason=%s", reason)
            return _keyword_fallback(text, title)

        return result

    @staticmethod
    def extract_skills(text: str, title: str = "") -> list[str]:
        """Back-compat shim: returns just the grounded skills list."""
        return LLMSkillExtractor.extract(text, title)["skills"]
