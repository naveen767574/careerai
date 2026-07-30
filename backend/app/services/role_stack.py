"""
Role & stack detection + skill filtering.

Pure, dependency-free helpers (no imports from recommendation_engine, so this
can be imported anywhere without a cycle). Used to make internship matching
ROLE-AWARE and STACK-AWARE:

  1. detect_role(title, description, skills)  -> (role_type, role_label)
  2. detect_stack(title, description, skills, role_type) -> (stack_type, stack_label)
  3. filter_relevant_skills(skills, stack)    -> [skills] with alternative
     language stacks removed (e.g. a Python backend job stops listing java/go/spring)

Design principles:
  • STACK IS ROLE-GATED. The stack a role reports must belong to the same
    category as the role. A Data role reports a DATA_SCIENCE stack, an ML role
    reports MACHINE_LEARNING — NEVER a language-backend stack like "Go Backend".
    Only BACKEND / FULLSTACK / GENERAL roles resolve to a concrete language
    stack (Python vs Node vs Java vs ...), because that distinction only makes
    sense for server-side work.
  • Alternative backend LANGUAGE stacks are MUTUALLY EXCLUSIVE. A job almost
    never requires Django AND Spring AND Express together — those come from a
    noisy scrape. filter_relevant_skills keeps only the dominant language
    stack's skills and drops the competing ones.
  • Matching is TOKEN-BOUNDED. "go" must not match inside "django"/"mongodb",
    "java" must not match inside "javascript". We use word-boundary regexes,
    not naive substring `in`.
  • Stack-neutral skills (rest api, sql, docker, git, aws...) are ALWAYS kept —
    they are not tied to any single language.
  • Conservative: if no language stack clearly dominates, we keep everything.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple


def _norm(value: object) -> str:
    return str(value).strip().lower() if value is not None else ""


def _signal_in(signal: str, text: str) -> bool:
    """
    True if `signal` occurs in `text` as a whole token (not embedded in a larger
    alphanumeric word).

    Boundaries treat [a-z0-9] as "word" characters, so:
        _signal_in("go", "django")      -> False   (embedded in djan|go)
        _signal_in("go", "go, python")  -> True
        _signal_in("java", "javascript")-> False   (embedded in java|script)
        _signal_in("node.js", "node.js")-> True

    Both arguments are expected already lowercased. Never raises.
    """
    if not signal:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(signal) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


# ---------------------------------------------------------------------------
# Role detection
# ---------------------------------------------------------------------------
# Ordered most-specific -> most-general. First group with a keyword hit wins,
# so "machine learning engineer" resolves to ML_ROLE before BACKEND_ROLE even
# though it may also mention Python.
#
# Labels are the SHORT display names the UI shows on badges. Keep them clean:
#   DATA_ROLE -> "Data Science", BACKEND_ROLE -> "Backend", etc.

_ROLE_RULES: List[Tuple[str, str, Tuple[str, ...]]] = [
    ("ML_ROLE", "Machine Learning", (
        "machine learning", "ml engineer", "deep learning", "ai engineer",
        "artificial intelligence", "nlp", "computer vision", "pytorch",
        "tensorflow", "data scientist", "mlops", "llm",
    )),
    ("DATA_ROLE", "Data Science", (
        "data analyst", "data analytics", "data engineer", "business intelligence",
        "bi analyst", "etl", "data warehouse", "tableau", "power bi",
        "big data", "analytics", "data science",
    )),
    ("FRONTEND_ROLE", "Frontend", (
        "frontend", "front-end", "front end", "ui developer", "ui/ux",
        "react developer", "angular developer", "vue developer", "web designer",
    )),
    ("MOBILE_ROLE", "Mobile", (
        "mobile", "android", "ios", "flutter", "react native", "app developer",
    )),
    ("DEVOPS_ROLE", "DevOps / Cloud", (
        "devops", "site reliability", "sre", "cloud engineer", "platform engineer",
        "infrastructure", "kubernetes",
    )),
    ("SECURITY_ROLE", "Security", (
        "security", "cybersecurity", "penetration", "soc analyst", "infosec",
    )),
    ("FULLSTACK_ROLE", "Full-Stack", (
        "full stack", "full-stack", "fullstack", "mern", "mean",
    )),
    ("BACKEND_ROLE", "Backend", (
        "backend", "back-end", "back end", "server-side", "api developer",
        "microservices",
    )),
]


def detect_role(title: str, description: str = "", skills: Optional[List[str]] = None) -> Tuple[str, str]:
    """
    Infer the role_type + a human label from a job's title/description/skills.

    Title is weighted highest (it is the strongest signal), then description,
    then the skills list. Returns ("GENERAL_ROLE", "Software Engineer") when
    nothing matches.
    """
    title_l = _norm(title)
    desc_l = _norm(description)
    skills_l = " ".join(_norm(s) for s in (skills or []))

    # Title carries the most intent — check it first, in isolation.
    for role_type, label, keywords in _ROLE_RULES:
        if any(kw in title_l for kw in keywords):
            return role_type, label

    # Then the broader text blob.
    combined = f"{desc_l} {skills_l}"
    for role_type, label, keywords in _ROLE_RULES:
        if any(kw in combined for kw in keywords):
            return role_type, label

    return "GENERAL_ROLE", "Software Engineer"


# ---------------------------------------------------------------------------
# Stack detection
# ---------------------------------------------------------------------------
# STACK IS ROLE-GATED. Non-backend roles map to a single stack CATEGORY that
# always agrees with the role (never a language backend). Only backend / full-
# stack / general roles resolve to a concrete LANGUAGE stack.

# role_type -> (stack_type, stack_label) for roles whose stack is a category,
# not a backend language. This is the guarantee that a Data role can NEVER
# show "Go Backend".
_ROLE_STACK_CATEGORY: dict[str, Tuple[str, str]] = {
    "ML_ROLE":       ("MACHINE_LEARNING", "Machine Learning"),
    "DATA_ROLE":     ("DATA_SCIENCE", "Data Science"),
    "FRONTEND_ROLE": ("FRONTEND", "Frontend"),
    "MOBILE_ROLE":   ("MOBILE", "Mobile"),
    "DEVOPS_ROLE":   ("DEVOPS", "Cloud / DevOps"),
    "SECURITY_ROLE": ("SECURITY", "Security"),
}

# Roles for which a concrete backend LANGUAGE stack is meaningful.
_LANGUAGE_STACK_ROLES = {"BACKEND_ROLE", "FULLSTACK_ROLE", "GENERAL_ROLE"}

# Each language stack has signature skills. These groups are treated as
# alternatives to one another during skill filtering.
_STACK_SIGNATURES: dict[str, dict] = {
    "PYTHON_STACK": {
        "label": "Python Backend",
        "signals": {"python", "django", "fastapi", "flask", "celery", "sqlalchemy", "pyramid"},
    },
    "NODE_STACK": {
        "label": "Node.js Backend",
        "signals": {"node.js", "node", "express", "nestjs", "nest.js", "koa", "next.js"},
    },
    "JAVA_STACK": {
        "label": "Java Backend",
        "signals": {"java", "spring", "spring boot", "hibernate", "maven", "kotlin"},
    },
    "GO_STACK": {
        "label": "Go Backend",
        "signals": {"go", "golang", "gin", "fiber", "echo"},
    },
    "DOTNET_STACK": {
        "label": ".NET Backend",
        "signals": {"c#", ".net", "asp.net", "dotnet", "entity framework"},
    },
    "RUBY_STACK": {
        "label": "Ruby Backend",
        "signals": {"ruby", "ruby on rails", "rails", "sinatra"},
    },
    "PHP_STACK": {
        "label": "PHP Backend",
        "signals": {"php", "laravel", "symfony", "codeigniter"},
    },
}

# Every skill that participates in language-stack competition (union of all
# signatures). A skill in this set but NOT in the winning stack is an
# "alternative stack" skill and gets filtered out. Anything outside this set is
# stack-neutral and always kept.
_ALL_STACK_SKILLS: set = set().union(*(v["signals"] for v in _STACK_SIGNATURES.values()))


def _detect_language_stack(title: str, description: str, skills: Optional[List[str]]) -> Tuple[str, str]:
    """
    Detect the dominant backend LANGUAGE stack from title/description/skills.

    Scoring: title hits weigh 3, description/skills hits weigh 1, using
    TOKEN-BOUNDED matching (so "go" never matches "django"). Highest score wins.
    Returns ("", "") when there is no language-stack signal at all.
    """
    title_l = _norm(title)
    text_l = f"{_norm(description)} {' '.join(_norm(s) for s in (skills or []))}"

    scores: dict[str, int] = {}
    for stack_type, meta in _STACK_SIGNATURES.items():
        score = 0
        for sig in meta["signals"]:
            if _signal_in(sig, title_l):
                score += 3
            if _signal_in(sig, text_l):
                score += 1
        if score > 0:
            scores[stack_type] = score

    if not scores:
        return "", ""

    best_stack = max(scores, key=scores.get)
    return best_stack, _STACK_SIGNATURES[best_stack]["label"]


def detect_stack(
    title: str,
    description: str = "",
    skills: Optional[List[str]] = None,
    role_type: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Detect the stack for a job, GATED BY ROLE so the stack always agrees with
    the role category.

    • Non-backend roles (ML / Data / Frontend / Mobile / DevOps / Security)
      return their fixed stack category — e.g. DATA_ROLE -> ("DATA_SCIENCE",
      "Data Science"). They can NEVER report a language backend.
    • Backend / Full-Stack / General roles return the dominant backend LANGUAGE
      stack (Python vs Node vs Java vs ...), or ("", "") if none is evident.

    role_type is inferred from title/description/skills when not supplied, so
    existing callers that pass only text keep working and now get role-consistent
    results. Never raises.
    """
    if role_type is None:
        role_type, _ = detect_role(title, description, skills)

    # Role-gated category stacks (the guarantee against mismatched labels).
    if role_type in _ROLE_STACK_CATEGORY:
        return _ROLE_STACK_CATEGORY[role_type]

    # Only backend-family roles resolve to a concrete language stack.
    if role_type in _LANGUAGE_STACK_ROLES:
        return _detect_language_stack(title, description, skills)

    # Unknown role -> no stack.
    return "", ""


def filter_relevant_skills(skills: List[str], stack_type: str) -> List[str]:
    """
    Remove alternative-LANGUAGE-stack skills, keeping the winning stack + all
    stack-neutral skills.

    Example (stack_type = PYTHON_STACK):
        in:  ["python", "django", "java", "spring", "express", "rest api", "sql", "go"]
        out: ["python", "django", "rest api", "sql"]
        (java/spring/express/go dropped — they belong to competing stacks)

    Only language stacks (PYTHON_STACK, NODE_STACK, ...) trigger filtering.
    Category stacks (DATA_SCIENCE, MACHINE_LEARNING, FRONTEND, ...) and falsy /
    unknown values are a no-op — the list is returned unchanged (order and
    values preserved). Never raises.
    """
    if not stack_type or stack_type not in _STACK_SIGNATURES:
        return list(skills)

    keep_signals = _STACK_SIGNATURES[stack_type]["signals"]

    result: List[str] = []
    for skill in skills:
        skill_n = _norm(skill)
        # Stack-neutral (not part of any stack signature) -> always keep.
        if skill_n not in _ALL_STACK_SKILLS:
            result.append(skill)
        # Part of the winning stack -> keep.
        elif skill_n in keep_signals:
            result.append(skill)
        # else: belongs to a competing stack -> drop it.

    # Safety net: never return an empty list just because filtering was
    # aggressive — fall back to the original if we somehow removed everything.
    return result if result else list(skills)
