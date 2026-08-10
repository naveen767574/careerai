import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.experience import Experience
from app.models.internship import Internship
from app.models.internship_skill import InternshipSkill
from app.models.project import Project
from app.models.recommendation import Recommendation
from app.models.resume import Resume
from app.models.skill import Skill
from app.services.embedding_manager import EmbeddingManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton EmbeddingManager — one instance for the entire process lifetime.
#
# WHY: FastAPI creates a new RecommendationEngine(db) per request. Without
# this, each request creates a new EmbeddingManager() with an empty cache,
# making the in-memory cache useless across requests. With a module-level
# singleton, the cache persists for as long as the process runs — embeddings
# for common skills like "python" or "react" are computed exactly once.
# ---------------------------------------------------------------------------
_embedding_manager = EmbeddingManager()


# ---------------------------------------------------------------------------
# Output schema for InternshipRecommendation
# ---------------------------------------------------------------------------

@dataclass
class InternshipRecommendation:
    internship_id: int
    title: str
    company: str
    location: str
    application_url: str
    similarity_score: float
    match_percentage: float
    matched_skills: List[str]
    missing_skills: List[str]
    match_label: str
    # Composite score (semantic/domain/behavior richness) used ONLY for ranking.
    # Never displayed — match_percentage is the honest weighted-coverage number.
    ranking_score: float = 0.0


# ---------------------------------------------------------------------------
# FIX 1: EmbeddingCache — avoids recomputing the same embedding twice
#
# WHY: Without this, if a user has 10 skills and you score 50 internships,
# you call the embedding model 10×50 = 500 times for the exact same vectors.
# With this cache, those 10 embeddings are computed once and reused.
# ---------------------------------------------------------------------------

class EmbeddingCache:
    """
    In-memory embedding cache scoped to a single request lifecycle.

    Usage:
        cache = EmbeddingCache(embedding_manager)
        vec = cache.get("python")   # computed once, reused on repeat calls
    """

    def __init__(self, embedding_manager: EmbeddingManager):
        self._manager = embedding_manager
        self._store: Dict[str, List[float]] = {}

    def get(self, text: str) -> List[float]:
        if not text:
            return []
        key = text.strip().lower()
        if key not in self._store:
            self._store[key] = self._manager.get_embedding(key)
        return self._store[key]

    def get_many(self, texts: List[str]) -> List[List[float]]:
        """Batch-fetch embeddings, computing only the ones not yet cached."""
        return [self.get(t) for t in texts if t]


# ---------------------------------------------------------------------------
# FIX 2: JobAnalysisAgent — replaces the hardcoded _build_job_analysis()
#
# WHY: The old version always returned seniority_level=1.0 (hardcoded) and
# had no domain field. This agent infers seniority and domain from available
# data (title + skills + description if present) without requiring an LLM
# call, keeping it fast and free.
# ---------------------------------------------------------------------------

class JobAnalysisAgent:
    """
    Analyzes a job posting and returns structured fields.
    Works from title + skills as primary signal.
    Uses description as a bonus signal when non-empty.
    No LLM call — rule-based inference is fast and sufficient here.
    """

    # Seniority keywords mapped to a numeric level (used in scoring).
    # Level 1.0 = intern/junior, 2.0 = mid, 3.0 = senior
    _SENIORITY_MAP = {
        "intern":       1.0, "internship": 1.0, "trainee": 1.0,
        "junior":       1.2, "entry":      1.2, "entry-level": 1.2,
        "associate":    1.5,
        "mid":          2.0, "mid-level":  2.0, "intermediate": 2.0,
        "senior":       3.0, "sr":         3.0, "lead": 3.0,
        "principal":    3.5, "staff":      3.5,
        "manager":      3.0, "director":   4.0,
    }

    # Domain keywords — maps terms found in title/skills to a domain label
    _DOMAIN_MAP = {
        ("machine learning", "deep learning", "pytorch", "tensorflow",
         "nlp", "computer vision", "ai", "ml"):               "ai_ml",
        ("react", "vue", "angular", "frontend", "css", "html",
         "next.js", "ui", "ux"):                               "frontend",
        ("django", "fastapi", "flask", "node", "backend",
         "rest api", "graphql", "microservices"):              "backend",
        ("aws", "gcp", "azure", "devops", "kubernetes",
         "docker", "ci/cd", "terraform"):                      "devops",
        ("pandas", "numpy", "sql", "data analysis",
         "tableau", "power bi", "spark", "etl"):               "data",
        ("android", "ios", "flutter", "react native",
         "swift", "kotlin"):                                    "mobile",
        ("cybersecurity", "penetration testing", "soc",
         "siem", "ethical hacking"):                           "security",
    }

    def analyze(self, internship: Internship, required_skills: List[str]) -> Dict[str, Any]:
        title = (internship.title or "").lower()
        description = (internship.description or "").lower()
        company = (internship.company or "").lower()

        seniority_level = self._infer_seniority(title, description)
        domain = self._infer_domain(title, required_skills, description)

        # Build a searchable text blob for domain/embedding comparisons
        context_text = self._build_context_text(
            title=internship.title,
            company=internship.company,
            skills=required_skills,
            description=internship.description,
        )

        # Classify skills by importance for weighted scoring.
        # Returns {skill_name: weight_int} using SKILL_WEIGHTS tiers.
        skill_weights = SkillClassifier().classify(
            skills=required_skills,
            domain=domain,
            title=internship.title or "",
        )

        return {
            "internship_id": internship.id,
            "required_skills": required_skills,
            "seniority_level": seniority_level,   # now actually inferred, not hardcoded
            "domain": domain,
            "context_text": context_text,
            "skill_weights": skill_weights,       # {skill_name: int} for weighted scoring
        }

    def _infer_seniority(self, title: str, description: str) -> float:
        text = f"{title} {description}"
        for keyword, level in self._SENIORITY_MAP.items():
            if keyword in text:
                return level
        return 1.0  # default: treat as internship/entry level

    def _infer_domain(
        self, title: str, skills: List[str], description: str
    ) -> str:
        combined = f"{title} {description} {' '.join(skills)}".lower()
        for keywords, domain in self._DOMAIN_MAP.items():
            if any(kw in combined for kw in keywords):
                return domain
        return "general"

    def _build_context_text(
        self,
        title: Optional[str],
        company: Optional[str],
        skills: List[str],
        description: Optional[str],
    ) -> str:
        # Use title + skills as the primary signal for embeddings.
        # We intentionally exclude description here even when available:
        #   1. Description text becomes a long, unique cache key that bloats memory.
        #   2. A 300-char description blob creates noisy embeddings that dilute
        #      the clean skill-to-skill similarity signal.
        #   3. The pgvector embedding (computed at ingestion time from full description)
        #      already captures the semantic content of the description — we don't
        #      need to re-embed it here.
        # Result: "react node.js mongodb mern stack developer internship"
        parts = [title or ""] + skills
        return " ".join(p for p in parts if p).lower().strip()


# ---------------------------------------------------------------------------
# FIX 3: MatchScoringAgent — same logic, but now accepts EmbeddingCache
#
# WHY: The original recomputed user embeddings inside every skill-match call.
# Now it accepts a shared cache so user vectors are computed once per request.
# Also: domain_alignment now uses job_analysis["domain"] for better accuracy.
# ---------------------------------------------------------------------------

class MatchScoringAgent:
    """
    Scores a (user_profile, job_analysis) pair on 5 dimensions.
    Accepts an EmbeddingCache to avoid redundant model calls.
    """

    DEFAULT_WEIGHTS = {
        "semantic_similarity": 0.30,
        "skill_coverage":      0.25,
        "skill_depth":         0.20,
        "domain_alignment":    0.15,
        "seniority_alignment": 0.10,
    }
    DEFAULT_SKILL_MATCH_THRESHOLD = 0.70

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        skill_match_threshold: float = DEFAULT_SKILL_MATCH_THRESHOLD,
    ):
        self.weights = self._normalize_weights(weights or self.DEFAULT_WEIGHTS)
        self.skill_match_threshold = max(0.0, min(1.0, skill_match_threshold))
        self.embedding_manager = _embedding_manager  # use process-level singleton

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        total = sum(weights.values())
        if total <= 0:
            return self.DEFAULT_WEIGHTS.copy()
        return {k: float(v) / total for k, v in weights.items()}

    def score_match(
        self,
        user_profile: Dict[str, Any],
        job_analysis: Dict[str, Any],
        embedding_similarity: float,
        cache: Optional[EmbeddingCache] = None,
    ) -> Dict[str, Any]:
        """
        Compute composite match score.

        Args:
            user_profile:        Output of RecommendationEngine._build_user_profile()
            job_analysis:        Output of JobAnalysisAgent.analyze()
            embedding_similarity: Precomputed pgvector cosine similarity (0–1)
            cache:               Shared EmbeddingCache for this request
        """
        if cache is None:
            cache = EmbeddingCache(self.embedding_manager)

        semantic_similarity = self._clamp(embedding_similarity)

        required_skills = job_analysis.get("required_skills", [])
        matched_skills, missing_skills = self._semantic_skill_match(
            user_skills=user_profile.get("skills", []),
            required_skills=required_skills,
            cache=cache,
        )

        # Weighted scoring: pull per-skill weights set by JobAnalysisAgent
        skill_weights = job_analysis.get("skill_weights", {})

        skill_coverage     = self._compute_skill_coverage(required_skills, matched_skills, skill_weights)
        skill_depth        = self._compute_skill_depth(user_profile, matched_skills, required_skills, skill_weights, cache)
        domain_alignment   = self._compute_domain_alignment(user_profile, job_analysis, matched_skills, cache)
        seniority_alignment = self._compute_seniority_alignment(user_profile, job_analysis)

        composite_score = (
            semantic_similarity    * self.weights["semantic_similarity"]
            + skill_coverage       * self.weights["skill_coverage"]
            + skill_depth          * self.weights["skill_depth"]
            + domain_alignment     * self.weights["domain_alignment"]
            + seniority_alignment  * self.weights["seniority_alignment"]
        )
        composite_score = self._clamp(composite_score)  # no rounding — full precision stored

        return {
            "internship_id": int(job_analysis.get("internship_id", 0)),
            "composite_score": composite_score,
            # skill_coverage is the DISPLAYED match number (× 100). It is weighted
            # matched/total — honest, real-skill-overlap. The composite above is
            # used ONLY as a ranking tiebreaker, never shown. Kept unrounded here
            # so match_percentage carries full precision.
            "skill_coverage": skill_coverage,
            "signal_breakdown": {
                "semantic_similarity": round(semantic_similarity, 4),
                "skill_coverage":      round(skill_coverage, 4),
                "skill_depth":         round(skill_depth, 4),
                "domain_alignment":    round(domain_alignment, 4),
                "seniority_alignment": round(seniority_alignment, 4),
            },
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
        }

    # ------------------------------------------------------------------
    # Internal scoring helpers
    # ------------------------------------------------------------------

    def _semantic_skill_match(
        self,
        user_skills: List[Dict[str, Any]],
        required_skills: List[str],
        cache: EmbeddingCache,
    ) -> Tuple[List[str], List[str]]:
        from app.services.embedding_service import cosine_similarity

        user_skill_texts = [
            _normalize(s.get("name")) for s in user_skills if s.get("name")
        ]
        required_skill_texts = [_normalize(s) for s in required_skills if s]

        if not required_skill_texts or not user_skill_texts:
            return [], required_skill_texts

        # FIX: use cache — these were being recomputed 50× per request before
        user_embeddings     = cache.get_many(user_skill_texts)
        required_embeddings = cache.get_many(required_skill_texts)

        matched = []
        for skill_text, req_emb in zip(required_skill_texts, required_embeddings):
            if not req_emb:
                continue
            best = max(
                (cosine_similarity(u_emb, req_emb) for u_emb in user_embeddings if u_emb),
                default=0.0,
            )
            if best >= self.skill_match_threshold:
                matched.append(skill_text)

        missing = [s for s in required_skill_texts if s not in matched]
        return matched, missing

    def _compute_skill_coverage(
        self,
        required_skills: List[str],
        matched_skills: List[str],
        skill_weights: Dict[str, int],
    ) -> float:
        """
        Weighted skill coverage: sum-of-matched-weights / sum-of-all-weights.

        A job requiring python (core=5) + react (core=5) + git (optional=1)
        has total_weight=11. Matching python+react gives 10/11 ≈ 0.91,
        far better than matching git+react (1+5=6/11 ≈ 0.55).
        Flat count would give 2/3 ≈ 0.67 for BOTH — this is the fix.
        """
        if not required_skills:
            return 0.0
        fallback = SKILL_WEIGHTS["important"]
        total_w   = sum(skill_weights.get(s, fallback) for s in required_skills)
        if total_w == 0:
            return 0.0
        matched_w = sum(skill_weights.get(s, fallback) for s in matched_skills)
        return min(1.0, matched_w / total_w)

    def _compute_skill_depth(
        self,
        user_profile: Dict[str, Any],
        matched_skills: List[str],
        required_skills: List[str],
        skill_weights: Dict[str, int],
        cache: EmbeddingCache,
    ) -> float:
        if not matched_skills or not required_skills:
            return 0.0

        # Use weighted ratio so matching core skills boosts depth more than optionals
        fallback = SKILL_WEIGHTS["important"]
        total_w   = sum(skill_weights.get(s, fallback) for s in required_skills)
        matched_w = sum(skill_weights.get(s, fallback) for s in matched_skills)
        matched_ratio = (matched_w / total_w) if total_w > 0 else 0.0
        experience_years = float(user_profile.get("experience_years", 0.0))
        project_relevance = self._compute_project_relevance(user_profile, required_skills, cache)
        experience_factor = min(1.0, experience_years / max(1.0, len(required_skills)))

        w = {"matched_ratio": 0.45, "experience": 0.35, "project_relevance": 0.20}
        return min(1.0, (
            matched_ratio     * w["matched_ratio"]
            + experience_factor * w["experience"]
            + project_relevance * w["project_relevance"]
        ) / sum(w.values()))

    def _compute_project_relevance(
        self,
        user_profile: Dict[str, Any],
        required_skills: List[str],
        cache: EmbeddingCache,
    ) -> float:
        from app.services.embedding_service import cosine_similarity

        project_terms = [
            _normalize(t) for t in user_profile.get("project_technologies", []) if t
        ]
        if not project_terms or not required_skills:
            return 0.0

        # Instead of embedding a joined blob (unique string = always a cache miss),
        # embed each term individually (short strings = mostly cache hits) and
        # average the best similarity per required skill.
        # This reuses cached embeddings for terms like "python", "react", "sql".
        required_embeddings = cache.get_many(required_skills)
        project_embeddings  = cache.get_many(project_terms)

        if not required_embeddings or not project_embeddings:
            return 0.0

        scores = []
        for req_emb in required_embeddings:
            if not req_emb:
                continue
            best = max(
                (cosine_similarity(p_emb, req_emb) for p_emb in project_embeddings if p_emb),
                default=0.0,
            )
            scores.append(best)

        return float(sum(scores) / len(scores)) if scores else 0.0

    def _compute_domain_alignment(
        self,
        user_profile: Dict[str, Any],
        job_analysis: Dict[str, Any],
        matched_skills: List[str],
        cache: EmbeddingCache,
    ) -> float:
        from app.services.embedding_service import cosine_similarity

        required_skills = [
            _normalize(s) for s in job_analysis.get("required_skills", []) if s
        ]
        if not required_skills:
            return 0.0

        # Signal 1: skill overlap ratio (no embedding needed — pure set math)
        # "How much of the job's domain vocabulary does the user already speak?"
        user_skill_set = {
            _normalize(s.get("name")) for s in user_profile.get("skills", []) if s.get("name")
        }
        project_tech_set = {
            _normalize(t) for t in user_profile.get("project_technologies", []) if t
        }
        user_vocab = user_skill_set | project_tech_set | set(matched_skills)
        required_set = set(required_skills)

        if required_set:
            overlap_ratio = len(user_vocab & required_set) / len(required_set)
        else:
            overlap_ratio = 0.0

        # Signal 2: semantic similarity between user skills and required skills
        # Uses individual cached embeddings — no new blob embeddings needed.
        # Each skill like "react", "python" is already in cache from _semantic_skill_match.
        user_terms = [s for s in user_vocab if s]
        if user_terms and required_skills:
            user_embeddings    = cache.get_many(list(user_terms)[:10])  # cap at 10 to stay fast
            required_embeddings = cache.get_many(required_skills)

            sem_scores = []
            for req_emb in required_embeddings:
                if not req_emb:
                    continue
                best = max(
                    (cosine_similarity(u_emb, req_emb) for u_emb in user_embeddings if u_emb),
                    default=0.0,
                )
                sem_scores.append(best)

            semantic_alignment = float(sum(sem_scores) / len(sem_scores)) if sem_scores else 0.0
        else:
            semantic_alignment = 0.0

        # Blend: 40% exact overlap, 60% semantic alignment
        return min(1.0, 0.4 * overlap_ratio + 0.6 * semantic_alignment)

    def _compute_seniority_alignment(
        self, user_profile: Dict[str, Any], job_analysis: Dict[str, Any]
    ) -> float:
        experience_years = float(user_profile.get("experience_years", 0.0))
        seniority_level  = float(job_analysis.get("seniority_level", 1.0))
        if seniority_level <= 0 or experience_years <= 0:
            return 0.0
        return min(1.0, experience_years / max(1.0, seniority_level))

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))


# FIX 5: match_label — derived from score, not hardcoded
# ---------------------------------------------------------------------------

def _derive_match_label(score: float) -> str:
    """
    Generate a match label from the composite score (0-1 scale).

    CANONICAL thresholds — must stay in sync with
    routes/recommendations.py::_derive_match_label (which operates on the
    same score expressed as 0-100). Both express identical semantics:
        >=0.80 Excellent | >=0.70 Strong | >=0.60 Good | >=0.50 Partial | else Low
    """
    if score >= 0.80:
        return "Excellent Match"
    if score >= 0.70:
        return "Strong Match"
    if score >= 0.60:
        return "Good Match"
    if score >= 0.50:
        return "Partial Match"
    return "Low Match"


# ---------------------------------------------------------------------------
# Module-level normalize helper (shared across classes)
# ---------------------------------------------------------------------------

def _normalize(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


# ---------------------------------------------------------------------------
# Skill weighting constants
# ---------------------------------------------------------------------------

SKILL_WEIGHTS: Dict[str, int] = {
    "core":      5,
    "important": 3,
    "optional":  1,
}

# ---------------------------------------------------------------------------
# CANONICAL match thresholds (0-100 coverage scale)
# ---------------------------------------------------------------------------
# match_percentage is weighted skill coverage × 100. These thresholds are the
# SINGLE definition of High/Medium/Low + the alert gate, imported by the routes
# so every surface (stats counter, job alerts, labels) agrees. Do not fork them.
HIGH_MATCH_THRESHOLD    = 75.0   # High Match  (item #4): score >= 75
MEDIUM_MATCH_THRESHOLD  = 50.0   # Medium      (item #4): 50 <= score < 75
STRONG_MATCH_THRESHOLD  = 70.0   # job-alert gate + "you meet core reqs" copy (item #3)
ALL_MATCHED_THRESHOLD   = 90.0   # "All required skills matched" (item #2)


# ---------------------------------------------------------------------------
# SkillClassifier — classify job skills at score time (no schema change)
#
# WHY: InternshipSkill rows have no importance field. Rather than requiring
# a migration and re-scrape, we classify skills at scoring time using:
#   1. Title signal — a skill in the job title is always core
#   2. Domain signal — known central skills per domain are core
#   3. Peripheral heuristics — soft/tooling skills are optional
#   4. Everything else — important (middle tier)
# ---------------------------------------------------------------------------

class SkillClassifier:
    """
    Classifies a job's required skills into core / important / optional
    and returns the corresponding integer weight per SKILL_WEIGHTS.

    Usage:
        weights = SkillClassifier().classify(skills, domain="frontend", title="React Intern")
        # {"react": 5, "css": 5, "node.js": 3, "git": 1, ...}
    """

    # Skills that are structurally central to each domain.
    # A skill matching any entry here gets "core" weight.
    _DOMAIN_CORE: Dict[str, set] = {
        "ai_ml":    {
            "python", "machine learning", "deep learning", "pytorch", "tensorflow",
            "scikit-learn", "keras", "nlp", "computer vision", "hugging face",
            "llm", "transformers", "neural network",
        },
        "frontend": {
            "react", "vue", "angular", "javascript", "typescript",
            "html", "css", "next.js", "svelte", "tailwind",
        },
        "backend":  {
            "python", "java", "node.js", "django", "fastapi", "flask",
            "spring", "express", "go", "rust", "ruby on rails", "graphql",
            "rest api", "microservices",
        },
        "devops":   {
            "docker", "kubernetes", "aws", "gcp", "azure", "terraform",
            "ci/cd", "linux", "ansible", "helm", "jenkins",
        },
        "data":     {
            "python", "sql", "pandas", "spark", "hadoop", "dbt",
            "data analysis", "etl", "tableau", "power bi", "airflow",
        },
        "mobile":   {
            "android", "ios", "flutter", "react native", "swift", "kotlin",
            "xcode", "android studio",
        },
        "security": {
            "cybersecurity", "penetration testing", "soc", "siem",
            "network security", "ethical hacking", "vulnerability assessment",
        },
    }

    # Skills that are always peripheral — tooling, soft skills, process.
    # These default to "optional" regardless of domain.
    _OPTIONAL: frozenset = frozenset({
        "git", "github", "gitlab", "bitbucket",
        "jira", "confluence", "trello", "notion", "slack",
        "agile", "scrum", "kanban",
        "communication", "teamwork", "leadership", "problem solving",
        "time management", "presentation", "documentation",
        "ms office", "excel", "powerpoint", "word",
        "linux", "bash", "shell scripting",   # tooling; overridden to core for devops
    })

    def classify(
        self,
        skills: List[str],
        domain: str,
        title: str,
    ) -> Dict[str, int]:
        """
        Returns {normalised_skill_name: weight_int} for every skill in `skills`.
        Weights are drawn from SKILL_WEIGHTS (core=5, important=3, optional=1).
        """
        title_lower = _normalize(title)
        domain_cores = self._DOMAIN_CORE.get(domain, set())

        result: Dict[str, int] = {}
        for skill in skills:
            skill_n = _normalize(skill)
            if skill_n in title_lower or skill_n in domain_cores:
                tier = "core"
            elif skill_n in self._OPTIONAL and domain != "devops":
                # linux/bash are core for devops; optional elsewhere
                tier = "optional"
            else:
                tier = "important"
            result[skill_n] = SKILL_WEIGHTS[tier]

        return result

    def total_weight(self, skills: List[str], weights: Dict[str, int]) -> int:
        return sum(weights.get(_normalize(s), SKILL_WEIGHTS["important"]) for s in skills)

    def matched_weight(self, matched: List[str], weights: Dict[str, int]) -> int:
        return sum(weights.get(_normalize(s), SKILL_WEIGHTS["important"]) for s in matched)


# ---------------------------------------------------------------------------
# BehaviorProfile — derived from saved / applied internship history
#
# WHY: A user who has saved 10 React jobs and applied to 3 of them is
# clearly interested in frontend roles. Pure resume matching can't capture
# this intent signal — it only knows what the user has done, not what they
# want to do next. BehaviorProfile extracts that latent preference and feeds
# it into the ranking boost.
# ---------------------------------------------------------------------------

# Maximum boost added to a composite score (0-1 scale).
# 0.08 = 8 percentage points — enough to reorder near-ties without letting a
# weak base score leap into a higher label tier.
BEHAVIOR_MAX_BOOST: float = 0.08

# Minimum number of behavioral signals (saves + applications) before any boost
# is applied. Prevents a single accidental bookmark from distorting rankings.
BEHAVIOR_MIN_SIGNALS: int = 2

# Minimum signals needed for full confidence. Confidence scales linearly
# from 0 at MIN_SIGNALS up to 1.0 at CONFIDENCE_SCALE_SIGNALS.
BEHAVIOR_CONFIDENCE_SCALE: int = 10


@dataclass
class BehaviorProfile:
    """
    Summarises a user's internship interaction history as a skill-frequency map.

    Attributes:
        skill_weights   Normalised per-skill frequency (0-1, sums to 1.0).
                        Derived from skills of saved/applied internships with
                        status weighting (applied/offer/interview → 2×, saved → 1×).
        dominant_skills Top-N skill names by frequency — used for fast lookup.
        total_signals   Raw count of internships that contributed (saves + apps).
        has_data        False when the user has no save/apply history yet.
    """
    skill_weights:   Dict[str, float]
    dominant_skills: set
    total_signals:   int
    has_data:        bool

    @classmethod
    def empty(cls) -> "BehaviorProfile":
        return cls(skill_weights={}, dominant_skills=set(), total_signals=0, has_data=False)


class BehaviorProfileBuilder:
    """
    Builds a BehaviorProfile from a user's application history in one DB query.

    Status weighting rationale:
      • applied / interview / offer  → weight 2  (user committed action)
      • saved / rejected / withdrawn → weight 1  (expressed interest)

    This means a job the user actually applied to contributes twice as much
    to the skill signal as one they merely bookmarked.
    """

    # How much each status contributes to the skill signal
    STATUS_WEIGHTS: Dict[str, int] = {
        "applied":   2,
        "interview": 2,
        "offer":     2,
        "saved":     1,
        "rejected":  1,
        "withdrawn": 1,
    }

    def __init__(self, db: Session):
        self._db = db

    def build(self, user_id: int) -> BehaviorProfile:
        """
        Returns a BehaviorProfile for user_id.
        Falls back to BehaviorProfile.empty() if no history exists or on error.
        """
        try:
            return self._build(user_id)
        except Exception as exc:
            logger.warning(
                "behavior_profile.build_failed user_id=%d error=%s", user_id, exc
            )
            return BehaviorProfile.empty()

    def _build(self, user_id: int) -> BehaviorProfile:
        # Single query: join applications → internship_skills, aggregate by skill
        rows = self._db.execute(
            text("""
                SELECT
                    s.skill_name,
                    SUM(
                        CASE a.status
                            WHEN 'applied'   THEN 2
                            WHEN 'interview' THEN 2
                            WHEN 'offer'     THEN 2
                            ELSE 1
                        END
                    ) AS weighted_freq
                FROM applications a
                JOIN internship_skills s ON s.internship_id = a.internship_id
                WHERE a.user_id = :uid
                  AND a.status IN ('saved','applied','interview','offer','rejected','withdrawn')
                GROUP BY s.skill_name
                ORDER BY weighted_freq DESC
                LIMIT 50
            """),
            {"uid": user_id},
        ).fetchall()

        if not rows:
            return BehaviorProfile.empty()

        # Count raw interaction signals (deduplicated internship count)
        total_signals = self._db.execute(
            text("""
                SELECT COUNT(DISTINCT internship_id)
                FROM applications
                WHERE user_id = :uid
                  AND status IN ('saved','applied','interview','offer','rejected','withdrawn')
            """),
            {"uid": user_id},
        ).scalar() or 0

        if total_signals < BEHAVIOR_MIN_SIGNALS:
            return BehaviorProfile.empty()

        # Normalise weighted frequencies to [0, 1]
        raw: Dict[str, float] = {
            _normalize(row[0]): float(row[1]) for row in rows if row[0]
        }
        max_freq = max(raw.values()) if raw else 1.0
        skill_weights = {skill: freq / max_freq for skill, freq in raw.items()}

        dominant_skills = set(list(skill_weights.keys())[:10])  # top-10 skills

        logger.info(
            "behavior_profile.built user_id=%d signals=%d unique_skills=%d dominant=%s",
            user_id, total_signals, len(skill_weights),
            ", ".join(list(dominant_skills)[:5]),
        )

        return BehaviorProfile(
            skill_weights=skill_weights,
            dominant_skills=dominant_skills,
            total_signals=total_signals,
            has_data=True,
        )


def _compute_behavior_boost(
    required_skills: List[str],
    behavior_profile: BehaviorProfile,
) -> float:
    """
    Compute a ranking boost [0, BEHAVIOR_MAX_BOOST] based on how well a
    job's required skills overlap with the user's behavioral skill signal.

    Args:
        required_skills:  Normalised required skills for the internship.
        behavior_profile: Pre-built BehaviorProfile for the user.

    Returns:
        Float in [0, BEHAVIOR_MAX_BOOST].
    """
    if not behavior_profile.has_data or not required_skills:
        return 0.0

    # Overlap: sum of behavior weights for skills that appear in required_skills
    overlap = sum(
        behavior_profile.skill_weights.get(s, 0.0)
        for s in required_skills
    )

    # Normalise by the number of required skills (so longer skill lists
    # don't automatically score lower — we care about the density of overlap)
    overlap_ratio = min(1.0, overlap / len(required_skills))

    # Confidence scales up to 1.0 at BEHAVIOR_CONFIDENCE_SCALE signals
    confidence = min(
        1.0,
        (behavior_profile.total_signals - BEHAVIOR_MIN_SIGNALS)
        / max(1, BEHAVIOR_CONFIDENCE_SCALE - BEHAVIOR_MIN_SIGNALS),
    )

    return BEHAVIOR_MAX_BOOST * overlap_ratio * confidence


# ---------------------------------------------------------------------------
# RecommendationEngine — the orchestrator that wires all agents together
# ---------------------------------------------------------------------------

class RecommendationEngine:
    TOP_N = 20

    def __init__(self, db: Session):
        self.db              = db
        self.scoring_agent   = MatchScoringAgent()
        self.job_agent       = JobAnalysisAgent()

    def get_recommendations(
        self, user_id: int, limit: int = 20
    ) -> List[InternshipRecommendation]:
        resume = self.db.query(Resume).filter(Resume.user_id == user_id).first()
        if not resume:
            logger.info("recommendation_engine.no_resume user_id=%d", user_id)
            return []

        user_profile = self._build_user_profile(user_id)

        # FIX: build embedding cache once — shared across ALL internship scoring
        embedding_manager = self.scoring_agent.embedding_manager
        cache = EmbeddingCache(embedding_manager)

        # Pre-warm cache with user skill embeddings (computed once, reused 50× below)
        user_skill_texts = [_normalize(s.get("name")) for s in user_profile.get("skills", []) if s.get("name")]
        cache.get_many(user_skill_texts)
        logger.info("recommendation_engine.cache_warmed skills=%d", len(user_skill_texts))

        # Build behavior profile once — reused for every internship's boost computation
        behavior_profile = BehaviorProfileBuilder(self.db).build(user_id)
        if behavior_profile.has_data:
            logger.info(
                "recommendation_engine.behavior_profile_loaded user_id=%d signals=%d",
                user_id, behavior_profile.total_signals,
            )

        internships = self._fetch_active_internships()

        # PERF: fetch ALL embedding similarities in ONE query instead of 1-per-internship
        internship_ids = [i.id for i in internships]
        similarity_map = self._fetch_embedding_similarities_batch(user_id, internship_ids)

        results: List[InternshipRecommendation] = []

        for internship in internships:
            required_skills      = self._get_required_skills(internship)
            job_analysis         = self.job_agent.analyze(internship, required_skills)
            embedding_similarity = similarity_map.get(internship.id, 0.0)

            scored = self.scoring_agent.score_match(
                user_profile=user_profile,
                job_analysis=job_analysis,
                embedding_similarity=embedding_similarity,
                cache=cache,   # shared cache passed in
            )

            if scored["composite_score"] <= 0:
                continue

            # Apply behavior boost — boosts jobs whose required skills
            # match the user's save/apply history. Clamped to [0, 1].
            boost      = _compute_behavior_boost(required_skills, behavior_profile)
            final_score = self.scoring_agent._clamp(scored["composite_score"] + boost)

            # DISPLAYED match = weighted skill coverage (real matched/total), NOT
            # the composite. This is the honest number: 1 matched skill out of many
            # scores low, never floats to 56% off semantic/domain signal. The
            # composite (final_score) is kept only as the ranking key below.
            display_pct = round(self.scoring_agent._clamp(scored["skill_coverage"]) * 100, 1)

            results.append(
                InternshipRecommendation(
                    internship_id=internship.id,
                    title=internship.title,
                    company=internship.company,
                    location=internship.location,
                    application_url=internship.application_url,
                    similarity_score=scored["signal_breakdown"]["semantic_similarity"],
                    match_percentage=display_pct,
                    matched_skills=scored["matched_skills"],
                    missing_skills=scored["missing_skills"],
                    # Label derives from the DISPLAYED number (0-100) so chip and %
                    # never contradict each other.
                    match_label=_derive_match_label(display_pct / 100.0),
                    # Ranking key: full composite + behavior boost (not displayed).
                    ranking_score=final_score,
                )
            )

        # Rank by the composite tiebreaker (semantic/domain/behavior richness),
        # NOT by the displayed coverage %, so ordering keeps its nuance while the
        # shown number stays honest.
        results.sort(key=lambda r: getattr(r, "ranking_score", r.match_percentage / 100.0), reverse=True)
        results = results[: min(limit, self.TOP_N)]
        self._persist_recommendations(user_id, results)
        return results

    def refresh_for_user(self, user_id: int) -> dict:
        # Per-user advisory lock — prevents two concurrent refresh calls for the
        # same user from racing on DELETE + INSERT and hitting the unique constraint.
        # pg_try_advisory_xact_lock is non-blocking and auto-released on commit/rollback.
        lock_acquired = self.db.execute(
            text("SELECT pg_try_advisory_xact_lock(:key)"),
            {"key": user_id},
        ).scalar()
        if not lock_acquired:
            return {"recommendations": 0, "skipped": True}

        resume = self.db.query(Resume).filter(Resume.user_id == user_id).first()
        if not resume:
            return {"recommendations": 0}

        user_profile = self._build_user_profile(user_id)
        embedding_manager = self.scoring_agent.embedding_manager
        cache = EmbeddingCache(embedding_manager)

        user_skill_texts = [_normalize(s.get("name")) for s in user_profile.get("skills", []) if s.get("name")]
        cache.get_many(user_skill_texts)

        # Behavior profile: built BEFORE the DELETE so existing rows still
        # exist in applications — the profile itself isn't affected by the
        # recommendation delete that follows.
        behavior_profile = BehaviorProfileBuilder(self.db).build(user_id)
        if behavior_profile.has_data:
            logger.info(
                "refresh.behavior_profile_loaded user_id=%d signals=%d",
                user_id, behavior_profile.total_signals,
            )

        internships = self._fetch_top_internships_for_refresh(user_id)
        self.db.query(Recommendation).filter(Recommendation.user_id == user_id).delete()

        # Batch fetch all similarities upfront
        internship_ids = [i.id for i in internships]
        similarity_map = self._fetch_embedding_similarities_batch(user_id, internship_ids)

        count = 0
        # Collect high-match internships for job-alert notifications (generated after commit).
        # Tuple: (internship_id, title, company, pct, matched_skills)
        _high_match: list[tuple[int, str, str, float, list[str]]] = []
        # Scored rows buffered so we can rank by composite before persisting.
        # Tuple: (internship, display_pct, ranking_score, matched_skills, scored_dict)
        _scored_rows: list = []

        for internship in internships:
            required_skills      = self._get_required_skills(internship)
            job_analysis         = self.job_agent.analyze(internship, required_skills)
            embedding_similarity = similarity_map.get(internship.id, 0.0)

            scored = self.scoring_agent.score_match(
                user_profile=user_profile,
                job_analysis=job_analysis,
                embedding_similarity=embedding_similarity,
                cache=cache,
            )
            if scored["composite_score"] <= 0:
                continue

            boost       = _compute_behavior_boost(required_skills, behavior_profile)
            final_score = self.scoring_agent._clamp(scored["composite_score"] + boost)
            # DISPLAYED match = weighted skill coverage (real matched/total).
            # The composite (final_score) is used only to rank; it is NOT stored
            # as the shown percentage.
            pct         = round(self.scoring_agent._clamp(scored["skill_coverage"]) * 100, 1)
            matched     = scored["matched_skills"]
            _scored_rows.append((internship, pct, final_score, matched, scored))

        # Rank by the composite tiebreaker, then persist — so ordering keeps its
        # semantic/behavior nuance while the stored % stays honest coverage.
        _scored_rows.sort(key=lambda t: t[2], reverse=True)

        for internship, pct, _rank, matched, scored in _scored_rows:
            self.db.add(
                Recommendation(
                    user_id=user_id,
                    internship_id=internship.id,
                    similarity_score=scored["signal_breakdown"]["semantic_similarity"],
                    match_percentage=pct,
                    # Persist the SAME semantic matched/missing the score was built from,
                    # so read paths return them verbatim (no recompute, no drift).
                    matched_skills=matched,
                    missing_skills=scored["missing_skills"],
                )
            )
            count += 1

            # Collect jobs at or above the "Strong Match" threshold for job alerts.
            # STRONG_MATCH_THRESHOLD is on the same 0-100 coverage scale as pct.
            if pct >= STRONG_MATCH_THRESHOLD:
                _high_match.append((
                    internship.id,
                    internship.title or "",
                    internship.company or "",
                    pct,
                    matched,
                ))

        self.db.commit()

        # ── Generate job-alert notifications (best-effort, never fails the refresh) ──
        if _high_match:
            try:
                from app.services.notification_service import NotificationService
                notif_service = NotificationService(self.db)
                created = 0
                for iid, title, company, pct, matched_skills in _high_match:
                    if notif_service.create_job_alert_if_new(
                        user_id=user_id,
                        internship_id=iid,
                        title=title,
                        company=company,
                        match_pct=pct,
                        matched_skills=matched_skills,
                    ):
                        created += 1
                if created:
                    logger.info("job_alerts.created user_id=%d count=%d", user_id, created)
            except Exception as exc:
                logger.error("job_alerts.trigger_failed user_id=%d error=%s", user_id, exc)
                # Never crash the refresh because notification creation failed.

        return {"recommendations": count}

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _fetch_active_internships(self) -> List[Internship]:
        return self.db.query(Internship).filter(Internship.is_active == True).all()

    def _get_required_skills(self, internship: Internship) -> List[str]:
        """Consolidate skills from InternshipSkill table + internship.required_skills field.

        Then apply STACK FILTERING: if the job clearly targets one backend stack
        (e.g. Python), drop skills that belong to competing stacks (java, spring,
        express, go...). Those almost always come from noisy scrapes — a single
        job rarely requires Django AND Spring AND Express together. Filtering here
        (at the source) means the cleaned list flows into scoring AND the stored
        matched/missing skills, so every downstream surface (card, skill-gap,
        explain) shows a relevant, non-contradictory skill set.
        """
        # Using .all() with scalar column query returns list of single-value tuples in SA 1.x
        # We unpack with [row[0]] pattern to stay compatible with both SA 1.x and 2.x
        rows = (
            self.db.query(InternshipSkill.skill_name)
            .filter(InternshipSkill.internship_id == internship.id)
            .all()
        )
        # Each row is a named tuple like (skill_name,) — extract the value
        from_table = [row[0] for row in rows if row[0]]
        skills = [_normalize(s) for s in from_table if s]

        if internship.required_skills:
            skills.extend(_normalize(s) for s in internship.required_skills if s)

        # Deduplicate while preserving order
        skills = list(dict.fromkeys(s for s in skills if s))

        # Stack-aware filtering — remove alternative-stack noise.
        try:
            from app.services.role_stack import detect_stack, filter_relevant_skills
            stack_type, _ = detect_stack(
                title=internship.title or "",
                description=internship.description or "",
                skills=skills,
            )
            if stack_type:
                skills = filter_relevant_skills(skills, stack_type)
        except Exception as exc:  # never let filtering break scoring
            logger.warning("required_skills.stack_filter_failed id=%s error=%s", internship.id, exc)

        return skills


    def _build_user_profile(self, user_id: int) -> Dict[str, Any]:
        skills      = self.db.query(Skill).filter(Skill.user_id == user_id).all()
        experiences = self.db.query(Experience).filter(Experience.user_id == user_id).all()
        projects    = self.db.query(Project).filter(Project.user_id == user_id).all()

        normalized_skills = [
            {"name": _normalize(s.skill_name), "category": _normalize(s.category)}
            for s in skills if s.skill_name
        ]

        total_months = sum(
            self._estimate_months(e.start_date, e.end_date) for e in experiences
        )

        project_technologies = list({
            _normalize(token)
            for p in projects if p.technologies
            for token in p.technologies.split(",")
            if token.strip()
        })

        return {
            "skills": normalized_skills,
            "experiences": [
                {
                    "role":        _normalize(e.role),
                    "company":     _normalize(e.company),
                    "description": _normalize(e.description),
                    "months":      self._estimate_months(e.start_date, e.end_date),
                }
                for e in experiences
            ],
            "projects": [
                {"name": _normalize(p.name), "description": _normalize(p.description)}
                for p in projects
            ],
            "project_technologies": project_technologies,
            "experience_years":     round(total_months / 12.0, 2),
        }

    def _fetch_embedding_similarities_batch(
        self, user_id: int, internship_ids: List[int]
    ) -> Dict[int, float]:
        """
        Fetch cosine similarities for ALL internships in ONE DB round-trip.

        Old approach: 50 internships = 50 separate SQL queries (~10–12s).
        New approach: 1 query returning all similarities at once (<0.5s).

        Uses string-interpolated IN clause because SQLAlchemy 1.x does not
        support passing a list to ANY(:param) in raw text queries.
        IDs are integers from the DB so interpolation is safe here.
        """
        if not internship_ids:
            return {}

        # Safe: internship_ids are ints fetched directly from DB, not user input
        ids_sql = ",".join(str(i) for i in internship_ids)

        result = self.db.execute(
            text(f"""
                SELECT i.id, 1 - (i.embedding <=> r.embedding) AS similarity
                FROM internships i
                JOIN resumes r ON r.user_id = :user_id
                WHERE i.id IN ({ids_sql})
                  AND i.embedding IS NOT NULL
                  AND r.embedding IS NOT NULL
            """),
            {"user_id": user_id},
        ).fetchall()

        return {row[0]: float(row[1]) for row in result if row[1] is not None}

    def _fetch_embedding_similarity(self, user_id: int, internship_id: int) -> float:
        """Single-internship fetch — kept for use in refresh_for_user."""""
        result = self.db.execute(
            text("""
                SELECT 1 - (i.embedding <=> r.embedding) AS similarity
                FROM internships i
                JOIN resumes r ON r.user_id = :user_id
                WHERE i.id = :internship_id
                  AND i.embedding IS NOT NULL
                  AND r.embedding IS NOT NULL
            """),
            {"user_id": user_id, "internship_id": internship_id},
        ).scalar_one_or_none()

        return float(result) if result is not None else 0.0

    def _estimate_months(
        self, start_date: Optional[date], end_date: Optional[date]
    ) -> int:
        if not start_date:
            return 0
        end = end_date or date.today()
        return max(0, (end.year - start_date.year) * 12 + (end.month - start_date.month))

    def _persist_recommendations(
        self, user_id: int, recommendations: List[InternshipRecommendation]
    ) -> None:
        # SA 1.x compatible: use .query() not select().scalars()
        existing = (
            self.db.query(Recommendation)
            .filter(Recommendation.user_id == user_id)
            .all()
        )
        existing_map = {r.internship_id: r for r in existing}

        for rec in recommendations:
            record = existing_map.get(rec.internship_id)
            if record:
                record.similarity_score = rec.similarity_score
                record.match_percentage = rec.match_percentage
                record.matched_skills = rec.matched_skills
                record.missing_skills = rec.missing_skills
                self.db.add(record)
            else:
                self.db.add(
                    Recommendation(
                        user_id=user_id,
                        internship_id=rec.internship_id,
                        similarity_score=rec.similarity_score,
                        match_percentage=rec.match_percentage,
                        matched_skills=rec.matched_skills,
                        missing_skills=rec.missing_skills,
                    )
                )
        self.db.commit()

    def _fetch_top_internships_for_refresh(self, user_id: int) -> List[Internship]:
        result = self.db.execute(
            text("""
                SELECT i.id
                FROM internships i
                JOIN resumes r ON r.user_id = :user_id
                WHERE i.embedding IS NOT NULL
                  AND r.embedding IS NOT NULL
                  AND i.is_active = true
                ORDER BY i.embedding <=> r.embedding
                LIMIT 50
            """),
            {"user_id": user_id},
        ).fetchall()

        if not result:
            return self._fetch_active_internships()

        internship_ids = [row.id for row in result if row.id is not None]
        return self.db.query(Internship).filter(Internship.id.in_(internship_ids)).all()
