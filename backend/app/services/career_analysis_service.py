"""
Role-aware career intelligence service.

Calls Groq LLaMA with a structured prompt and returns a validated dict.
All parsing is safe — never raises on bad LLM output.

The LLM produces the qualitative analysis (role, skills, priorities, plans).
The readiness_score is computed in Python from that output so the headline
number is deterministic and grounded — never a hallucinated metric.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from groq import Groq

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a senior career coach and technical hiring expert specialising in Indian
tech and internship markets.

You receive a candidate's resume text and return a structured JSON analysis.
Think like a mentor guiding one specific student — not a keyword scanner.

STRICT RULES:
1. Infer the target role from the candidate's skills, projects, and experience.
   Do NOT rely on a stated objective — infer it from evidence.
2. present_skills must be ONLY skills explicitly mentioned in the resume text.
   Do NOT invent skills.
3. missing_skills must be role-relevant gaps — NOT generic "communication" unless
   it genuinely blocks the role. Do NOT list skills already in present_skills.
4. Every entry in missing_skills_detailed MUST include a priority:
   - "High"   -> a must-have the role requires; you can't get hired without it.
   - "Medium" -> useful and expected, but not an immediate blocker.
   - "Low"    -> a bonus / nice-to-have that differentiates candidates.
   Be honest — most roles have only 2-4 truly High-priority gaps.
5. match_score: realistic 0-100 based on present vs required skills.
   Do NOT give > 90 unless the resume is near-perfect for the role.
6. how_to_learn: concrete steps (course names, platforms, GitHub project ideas).
   Not vague advice like "read the docs".
7. missing_experience: real-world experience gaps, NOT skills — e.g.
   "No model deployment experience", "No end-to-end pipeline work",
   "No production/real-world projects". Empty list if none apply.
8. recommended_projects: 2-4 concrete portfolio projects that would close the
   biggest gaps for THIS role. Each is one short buildable project title.
9. action_plan: a realistic 7-day kickstart. 3-4 entries covering Day 1 through
   Day 7, each with a "day" range and a short concrete "focus". Beginner-friendly.
10. readiness_summary: ONE short sentence on how job-ready the candidate is for
    the role. Do NOT state a percentage — the system computes the number.
11. career_guidance: write like a mentor speaking directly to the student.
    Reference what they have and what to build next. Be specific.
12. resume_improvements: 3-5 actionable bullet suggestions grounded in the actual
    resume. Do NOT fabricate metrics or placeholders like [X%].
13. Return ONLY valid JSON — no markdown, no prose outside the JSON object.
"""

_USER_TEMPLATE = """\
Analyze this resume and return the JSON schema exactly.

RESUME TEXT:
{resume_text}

Return this exact JSON structure (fill every field):
{{
  "target_role": "string — inferred job title e.g. 'ML Engineer', 'Frontend Developer'",
  "confidence": 0-100,
  "reasoning": "1-2 sentences explaining why this role was inferred",
  "match_score": 0-100,
  "level": "Fresher | Junior | Mid-Level | Senior",
  "role_analysis": "2-3 sentences: what the role demands vs. what the candidate brings",
  "readiness_summary": "1 sentence on job-readiness for this role (NO percentage)",
  "present_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1", "skill2"],
  "missing_skills_detailed": [
    {{
      "skill": "skill name",
      "priority": "High | Medium | Low",
      "why_it_matters": "1 sentence — concrete reason this skill matters for the role",
      "how_to_learn": ["Step 1: ...", "Step 2: ...", "Step 3: ..."],
      "project_idea": "One concrete project the candidate can build to demonstrate this skill"
    }}
  ],
  "missing_experience": ["e.g. No model deployment experience", "No end-to-end pipeline work"],
  "recommended_projects": ["Concrete project 1", "Concrete project 2"],
  "action_plan": [
    {{ "day": "Day 1-2", "focus": "short concrete task" }},
    {{ "day": "Day 3-4", "focus": "short concrete task" }},
    {{ "day": "Day 5-7", "focus": "short concrete task" }}
  ],
  "career_guidance": "3-5 sentences of mentor-style guidance specific to this candidate",
  "resume_improvements": ["improvement 1", "improvement 2", "improvement 3"]
}}
"""

# ---------------------------------------------------------------------------
# Fallback schema — returned on any failure so the API never 500s
# ---------------------------------------------------------------------------

_FALLBACK: dict[str, Any] = {
    "target_role": "Software Engineer",
    "confidence": 0,
    "reasoning": "Unable to analyse resume at this time.",
    "match_score": 0,
    "level": "Fresher",
    "role_analysis": "",
    "readiness_score": 0,
    "readiness_summary": "",
    "present_skills": [],
    "missing_skills": [],
    "missing_skills_detailed": [],
    "missing_experience": [],
    "recommended_projects": [],
    "action_plan": [],
    "career_guidance": "",
    "resume_improvements": [],
    "_error": True,
}

# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?(.*?)```", re.DOTALL)


def _extract_json(raw: str) -> str:
    """Strip markdown fences and find the outermost { } block."""
    # Remove fences if present
    m = _FENCE_RE.search(raw)
    if m:
        raw = m.group(1).strip()

    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        return raw[start:end]
    return raw


def _coerce_int(val: Any, lo: int = 0, hi: int = 100) -> int:
    try:
        return max(lo, min(hi, int(float(val))))
    except (TypeError, ValueError):
        return lo


def _coerce_str(val: Any) -> str:
    return str(val).strip() if val else ""


def _coerce_list_of_str(val: Any) -> list[str]:
    if not isinstance(val, list):
        return []
    return [str(v).strip() for v in val if str(v).strip()]


_PRIORITIES = ("High", "Medium", "Low")


def _coerce_priority(val: Any) -> str:
    s = str(val).strip().capitalize() if val else ""
    return s if s in _PRIORITIES else "Medium"


def _coerce_detailed(val: Any) -> list[dict]:
    if not isinstance(val, list):
        return []
    out = []
    for item in val:
        if not isinstance(item, dict):
            continue
        skill = _coerce_str(item.get("skill"))
        if not skill:
            continue
        out.append({
            "skill":          skill,
            "priority":       _coerce_priority(item.get("priority")),
            "why_it_matters": _coerce_str(item.get("why_it_matters")),
            "how_to_learn":   _coerce_list_of_str(item.get("how_to_learn")),
            "project_idea":   _coerce_str(item.get("project_idea")),
        })
    # Surface must-haves first: High -> Medium -> Low, order stable otherwise.
    order = {"High": 0, "Medium": 1, "Low": 2}
    out.sort(key=lambda d: order.get(d["priority"], 1))
    return out


def _coerce_action_plan(val: Any) -> list[dict]:
    """Normalise the 7-day plan to a list of {day, focus}."""
    if not isinstance(val, list):
        return []
    out: list[dict] = []
    for item in val:
        if isinstance(item, dict):
            day   = _coerce_str(item.get("day"))
            focus = _coerce_str(item.get("focus") or item.get("task") or item.get("activity"))
            if focus:
                out.append({"day": day or f"Day {len(out) + 1}", "focus": focus})
        elif isinstance(item, str) and item.strip():
            out.append({"day": f"Day {len(out) + 1}", "focus": item.strip()})
        if len(out) >= 7:
            break
    return out


# ---------------------------------------------------------------------------
# Readiness score — computed in Python, NOT taken from the LLM
# ---------------------------------------------------------------------------

_PRIORITY_PENALTY = {"High": 6.0, "Medium": 3.0, "Low": 1.0}


def _compute_readiness(match_score: int, detailed: list[dict], missing_experience: list[str]) -> int:
    """
    Derive a job-readiness score from the (grounded) LLM analysis.

    Starts from the role match score, then applies a bounded penalty for
    high-priority skill gaps and missing real-world experience. Deterministic,
    so the headline number can never be a hallucinated metric.
    """
    score = float(match_score)

    penalty = 0.0
    for s in detailed:
        penalty += _PRIORITY_PENALTY.get(s.get("priority", "Medium"), 3.0)
    penalty += 4.0 * len(missing_experience)

    # Cap so a long list of minor gaps can't collapse readiness to zero.
    penalty = min(penalty, 40.0)

    # Apply half the penalty weight so readiness tracks match_score closely.
    readiness = round(score - 0.5 * penalty)
    return max(5, min(95, readiness))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(data: dict) -> dict:
    """Coerce every field to the expected type — never raises."""
    match_score        = _coerce_int(data.get("match_score"))
    detailed           = _coerce_detailed(data.get("missing_skills_detailed"))
    missing_experience = _coerce_list_of_str(data.get("missing_experience"))

    return {
        "target_role":            _coerce_str(data.get("target_role")) or "Software Engineer",
        "confidence":             _coerce_int(data.get("confidence")),
        "reasoning":              _coerce_str(data.get("reasoning")),
        "match_score":            match_score,
        "level":                  _coerce_str(data.get("level")) or "Fresher",
        "role_analysis":          _coerce_str(data.get("role_analysis")),
        "readiness_score":        _compute_readiness(match_score, detailed, missing_experience),
        "readiness_summary":      _coerce_str(data.get("readiness_summary")),
        "present_skills":         _coerce_list_of_str(data.get("present_skills")),
        "missing_skills":         _coerce_list_of_str(data.get("missing_skills")),
        "missing_skills_detailed": detailed,
        "missing_experience":     missing_experience,
        "recommended_projects":   _coerce_list_of_str(data.get("recommended_projects")),
        "action_plan":            _coerce_action_plan(data.get("action_plan")),
        "career_guidance":        _coerce_str(data.get("career_guidance")),
        "resume_improvements":    _coerce_list_of_str(data.get("resume_improvements")),
    }


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def analyse_career(resume_text: str) -> dict[str, Any]:
    """
    Run the role-aware career analysis against Groq LLaMA.

    Returns a validated dict matching the schema above.
    On any failure (API error, bad JSON, timeout) returns _FALLBACK
    so the caller always gets a safe dict — never raises.
    """
    if not resume_text or not resume_text.strip():
        return dict(_FALLBACK)

    api_key = getattr(settings, "GROQ_API_KEY", None)
    if not api_key:
        logger.warning("career_analysis: GROQ_API_KEY not set — returning fallback")
        return dict(_FALLBACK)

    # Trim resume to keep context window manageable (avoid 8k-token overflow).
    trimmed = resume_text.strip()[:6000]

    user_message = _USER_TEMPLATE.format(resume_text=trimmed)

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",   # stronger model for structured reasoning
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.2,
            max_tokens=2560,
            response_format={"type": "json_object"},
        )
        raw = (response.choices[0].message.content or "").strip()
        logger.info("career_analysis.raw_length=%d", len(raw))
    except Exception as exc:
        logger.error("career_analysis.groq_failed: %s", exc)
        return dict(_FALLBACK)

    try:
        clean = _extract_json(raw)
        data  = json.loads(clean)
        result = _validate(data)
        logger.info(
            "career_analysis.ok role=%s match=%d readiness=%d confidence=%d",
            result["target_role"], result["match_score"],
            result["readiness_score"], result["confidence"],
        )
        return result
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.error("career_analysis.parse_failed: %s | raw=%s", exc, raw[:300])
        return dict(_FALLBACK)
