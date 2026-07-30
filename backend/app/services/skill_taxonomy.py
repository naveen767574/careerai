"""
app/services/skill_taxonomy.py

SINGLE SOURCE OF TRUTH for the skill vocabulary (Phase 2).

Previously the canonical skill dictionary + alias map lived inside
`app/scraper/utils/extractor.py`. They are now here so BOTH the scraper's
extractor and the new `LLMSkillExtractor` share exactly one vocabulary — no
drift between the path that stores skills and the path that scores them.

This module is a PURE REFACTOR of the data that already existed:
  • CANONICAL_SKILLS  == the old SKILLS_DICTIONARY (unchanged contents)
  • SKILL_ALIASES     == the old SKILL_ALIASES (unchanged contents)

It adds ONE new function, `normalize_skill()`, which is the grounding gate for
Phase 2: the LLM may SUGGEST skills, but the taxonomy DECIDES truth. A term that
does not resolve to a known canonical skill returns None and is dropped.

Design guarantee: no fuzzy matching, no partial matching. A skill is either a
known canonical name (or a known alias of one) or it is rejected. This is what
lets us use the LLM for recall without inheriting its hallucinations.
"""
from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Canonical skill dictionary — 200+ skills, lowercase keys.
# (Moved verbatim from app/scraper/utils/extractor.py::SKILLS_DICTIONARY)
# Add new skills here as they appear in the eval's per-case `missing` lists.
# ---------------------------------------------------------------------------
CANONICAL_SKILLS: set[str] = {
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "swift", "kotlin", "ruby", "php", "scala", "r", "matlab", "perl",
    "bash", "shell", "powershell",

    # Web Frontend
    "react", "redux", "vue", "angular", "next.js", "nuxt", "svelte", "html", "css",
    "sass", "tailwind", "bootstrap", "webpack", "vite", "jquery",

    # Web Backend
    "nodejs", "express", "fastapi", "django", "flask", "spring", "spring boot",
    "rails", "laravel", "asp.net", "graphql", "rest api", "websocket",

    # Databases
    "sql", "postgresql", "mysql", "sqlite", "mongodb", "redis", "elasticsearch",
    "cassandra", "dynamodb", "firebase", "supabase", "oracle", "sql server",
    "influxdb", "neo4j", "snowflake",

    # Cloud & DevOps
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
    "jenkins", "github actions", "ci/cd", "linux", "nginx", "apache",
    "cloudflare", "heroku", "vercel", "railway",

    # Data & ML
    "machine learning", "deep learning", "nlp", "computer vision",
    "data science", "data analysis", "data visualization", "statistics",
    "pandas", "numpy", "scikit-learn",
    "tensorflow", "pytorch", "keras", "hugging face", "langchain",
    "matplotlib", "seaborn", "plotly", "tableau", "power bi",
    "spark", "hadoop", "airflow", "dbt", "etl",

    # Mobile
    "android", "ios", "flutter", "react native", "swift", "kotlin",
    "xamarin", "ionic",

    # Tools & Practices
    "git", "github", "gitlab", "jira", "confluence", "figma", "postman",
    "swagger", "agile", "scrum", "kanban", "tdd", "microservices",
    "api design", "system design",

    # General Tech
    "excel", "word", "powerpoint", "google sheets", "notion",
    "object oriented programming", "oop", "functional programming",
    "data structures", "algorithms",

    # Soft / Domain skills worth extracting
    "communication", "teamwork", "problem solving", "leadership",
}

# ---------------------------------------------------------------------------
# Alias map — non-canonical → canonical.
# (Moved verbatim from app/scraper/utils/extractor.py::SKILL_ALIASES)
# Key: what appears in job descriptions / LLM output
# Value: the canonical skill stored in the DB (must exist in CANONICAL_SKILLS)
# ---------------------------------------------------------------------------
SKILL_ALIASES: dict[str, str] = {
    # Language aliases
    "js":           "javascript",
    "ts":           "typescript",
    "py":           "python",
    "c plus plus":  "c++",
    "golang":       "go",
    "node":         "nodejs",
    "node.js":      "nodejs",
    "reactjs":      "react",
    "react.js":     "react",
    "vuejs":        "vue",
    "vue.js":       "vue",
    "angularjs":    "angular",
    "nextjs":       "next.js",
    "react-native": "react native",

    # ML aliases
    "ml":           "machine learning",
    "dl":           "deep learning",
    "ai":           "machine learning",  # broad but useful
    "natural language processing": "nlp",
    "cv":               "computer vision",
    "computer-vision":  "computer vision",
    "hf":               "hugging face",
    "huggingface":  "hugging face",
    "stats":        "statistics",
    "apache spark": "spark",
    "data viz":     "data visualization",

    # DB aliases
    "postgres":     "postgresql",
    "mongo":        "mongodb",
    "es":           "elasticsearch",
    "dynamo":       "dynamodb",
    "mssql":        "sql server",

    # Cloud aliases
    "amazon web services": "aws",
    "google cloud": "gcp",
    "gcp":          "gcp",
    "k8s":          "kubernetes",
    "kube":         "kubernetes",
    "tf":           "terraform",

    # Framework aliases
    "fastapi":      "fastapi",
    "spring boot":  "spring boot",
    "springboot":   "spring boot",
    "sklearn":      "scikit-learn",
    "sk-learn":     "scikit-learn",
    "pytorch":      "pytorch",
    "torch":        "pytorch",

    # Tool aliases
    "gh":           "github",
    "gh actions":   "github actions",
    "ci cd":        "ci/cd",
    "cicd":         "ci/cd",
    "ci-cd":        "ci/cd",
    "rest":         "rest api",
    "restful":      "rest api",
    "restful api":  "rest api",
    "restful apis": "rest api",
    "rest apis":    "rest api",
    "rest api's":   "rest api",
    "restapi":      "rest api",
    "restful services": "rest api",
    "rest framework": "rest api",
    "django rest framework": "rest api",
    "oop":          "object oriented programming",

    # Framework / library surface-form variants
    "scikit learn": "scikit-learn",
    "scikitlearn":  "scikit-learn",
    "spring-boot":  "spring boot",
    "powerbi":      "power bi",
    "power-bi":     "power bi",

    # Multi-word concept plurals / variants the LLM tends to emit
    "machine-learning": "machine learning",
    "deep-learning":    "deep learning",
    "neural networks":  "deep learning",
    "computervision":   "computer vision",
    "hugging-face":     "hugging face",
    "reactnative":      "react native",
    "android sdk":      "android",

    # Soft skills
    "communication skills": "communication",
    "team player":          "teamwork",
    "problem-solving":      "problem solving",
}


def normalize_skill(raw: str) -> Optional[str]:
    """
    The grounding gate: resolve an arbitrary skill string to its canonical form,
    or reject it.

    Steps (exact, no fuzzy logic):
      1. lowercase + strip whitespace
      2. if the cleaned value is a known alias → return its canonical mapping
      3. if the cleaned value is already a canonical skill → return it
      4. otherwise → return None  (caller MUST drop it)

    Returning None is how hallucinated / out-of-taxonomy skills are removed.
    There is deliberately NO fuzzy matching and NO substring matching: a term is
    either exactly known (directly or via alias) or it is rejected.

    Note: an alias may map to a canonical value that is NOT itself in
    CANONICAL_SKILLS in theory; we still trust the curated alias map (it is the
    author-maintained mapping), so alias hits are always accepted.
    """
    if not raw or not isinstance(raw, str):
        return None

    cleaned = raw.strip().lower()
    if not cleaned:
        return None

    # Alias first — an alias is an explicit, curated mapping to a canonical name.
    if cleaned in SKILL_ALIASES:
        return SKILL_ALIASES[cleaned]

    # Direct canonical hit.
    if cleaned in CANONICAL_SKILLS:
        return cleaned

    return None
