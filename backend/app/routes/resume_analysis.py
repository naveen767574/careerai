from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.recommendation import Recommendation
from app.models.resume import Resume
from app.models.resume_analysis import ResumeAnalysis
from app.services.auth_service import AuthService
from app.services.resume_optimizer import ResumeOptimizer

router = APIRouter()
security = HTTPBearer()

# Cap the number of bullets we send to the LLM per request (each is one Groq call).
MAX_BULLETS_TO_IMPROVE = 6
# Cap missing keywords returned for display.
MAX_MISSING_KEYWORDS = 12
# Cap skill-based resume suggestions.
MAX_SKILL_SUGGESTIONS = 8

import re

# Bullet glyphs commonly found (or mangled) in resume text after PDF/DOCX extraction.
_BULLET_MARKERS = "•‣●○▪–—·◦*-"

# Strong action verbs — a bullet that starts with one is treated as a real,
# and likely already-strong, accomplishment bullet.
_ACTION_VERBS = {
    "built", "designed", "implemented", "developed", "created", "led", "engineered",
    "architected", "automated", "optimized", "managed", "deployed", "integrated",
    "analyzed", "researched", "collaborated", "launched", "shipped", "improved",
    "reduced", "increased", "delivered", "streamlined", "spearheaded", "orchestrated",
    "migrated", "refactored", "scaled", "maintained", "tested", "debugged",
    "programmed", "coded", "trained", "deployed", "configured", "established",
}

# Common tech keywords used as a "specificity" signal.
_TECH_HINTS = {
    "python", "java", "javascript", "typescript", "react", "node", "fastapi",
    "django", "flask", "sql", "postgresql", "mongodb", "aws", "docker",
    "kubernetes", "api", "rest", "graphql", "ml", "nlp", "pytorch", "tensorflow",
    "redis", "kafka", "spark", "git", "ci/cd", "microservices", "llm",
}

_DATE_LINE_RE = re.compile(
    r"^\s*((jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*)?"
    r"((19|20)\d{2}|present|current|\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)
_SECTION_WORDS = {
    "experience", "employment", "work experience", "projects", "project",
    "education", "skills", "certifications", "summary", "objective",
    "achievements", "contact", "profile", "interests",
}

# Friendly labels for the analyzer's missing_sections codes.
_SECTION_LABELS = {
    "skills": "Add a skills section listing your key technologies.",
    "education": "Add an education section with your degree and institution.",
    "experience": "Add a work/internship experience section.",
    "projects": "Add a projects section to showcase what you've built.",
    "certifications": "Add relevant certifications to strengthen your profile.",
    "email": "Add a professional email address to your header.",
    "phone": "Add a phone number to your contact header.",
}


def _is_dateish(s: str) -> bool:
    """Line that is (mostly) a date or date range."""
    if _DATE_LINE_RE.match(s):
        return True
    digits = sum(c.isdigit() for c in s)
    return len(s) <= 24 and digits >= max(2, len(s) // 3)


def _is_header_or_title(s: str) -> bool:
    """Section header ('EXPERIENCE') or a job-title/company line, not an action bullet."""
    low = s.strip().lower().rstrip(":")
    if low in _SECTION_WORDS:
        return True
    words = s.split()
    # Short ALL-CAPS line → header.
    if len(words) <= 4 and s.upper() == s and any(c.isalpha() for c in s):
        return True
    # Title/company line: short, no action verb, looks like "Role at Company" / "Role | Company".
    first = words[0].lower().strip(_BULLET_MARKERS) if words else ""
    if len(words) <= 8 and first not in _ACTION_VERBS:
        if (" at " in f" {low} ") or ("|" in s) or ("—" in s and len(words) <= 6):
            return True
    return False


def _is_real_bullet(s: str) -> bool:
    """Keep only substantive accomplishment lines."""
    if len(s) < 25:            # too short to be a real accomplishment bullet
        return False
    if _is_dateish(s):
        return False
    if _is_header_or_title(s):
        return False
    words = s.split()
    if len(words) < 5:
        return False
    return True


def is_strong_bullet(s: str) -> bool:
    """
    A bullet is 'already strong' (skip the LLM, return unchanged) when it:
      - starts with a strong action verb, AND
      - is reasonably detailed (>= 8 words), AND
      - is specific (contains a number OR a known tech keyword).
    """
    words = s.split()
    if len(words) < 8:
        return False
    first = words[0].lower().strip(_BULLET_MARKERS + ".,")
    if first not in _ACTION_VERBS:
        return False
    has_number = any(c.isdigit() for c in s)
    has_tech = any(w.lower().strip(".,()") in _TECH_HINTS for w in words)
    # Require BOTH a number AND a tech keyword to skip the LLM. A bullet with
    # tech but no numbers should still go through so the LLM can improve framing.
    return has_number and has_tech


# Words that, when a line ENDS on them, signal the sentence continues on the
# next line — so the following fragment should be merged in.
_CONTINUATION_WORDS = {
    "that", "and", "to", "with", "using", "for", "of", "the", "a", "an",
    "in", "on", "by", "as", "from", "or", "which", "while", "into",
}


def _merge_connective(items: list[str]) -> list[str]:
    """
    Merge ONLY genuine sentence continuations: a fragment is appended to the
    previous line when that line has no terminal punctuation AND ends on a
    dangling connective word ("...a system that" + "handles context...").
    Separate bullets (previous ends on a normal word) are NOT merged.
    """
    out: list[str] = []
    for b in items:
        b = b.strip()
        if not b:
            continue
        if out:
            last = out[-1].rstrip()
            last_words = last.split()
            last_word = re.sub(r"[^a-z]", "", last_words[-1].lower()) if last_words else ""
            if not last.endswith((".", "!", "?")) and last_word in _CONTINUATION_WORDS:
                out[-1] = last + " " + b
                continue
        out.append(b)
    return out


def _extract_bullets(lines: list[str]) -> list[str]:
    """
    Extract real accomplishment bullets from a section's lines.

    - If the section uses bullet markers: each marker starts a new bullet, and
      following NON-marker lines are treated as continuations of that bullet
      (fixes wrapped bullets). Lines before the first marker (titles) are ignored.
    - Otherwise: each substantive line is a candidate; only true connective
      continuations are merged.
    Finally, filter out titles / dates / headers so ONLY genuine action bullets
    reach the LLM.
    """
    stripped = [(raw or "").strip() for raw in lines]
    has_markers = any(s[:1] in _BULLET_MARKERS for s in stripped if s)

    bullets: list[str] = []
    if has_markers:
        current: str | None = None
        for s in stripped:
            if not s:
                continue
            if s[0] in _BULLET_MARKERS:
                if current:
                    bullets.append(current)
                current = s.lstrip(_BULLET_MARKERS + " \t").strip()
            elif current is not None:
                current = (current + " " + s).strip()  # continuation of current bullet
            # lines before the first marker (section title / job title) are skipped
        if current:
            bullets.append(current)
    else:
        bullets = _merge_connective([s for s in stripped if s])

    return [b for b in bullets if _is_real_bullet(b)]


# Role-inference signal sets (used to infer target domain from detected skills).
# These drive recommendation filtering and LLM context — they are NOT returned
# to the user as keywords, so "no hardcoded keyword lists in output" is preserved.
# ---------------------------------------------------------------------------
# Per-skill resume-improvement suggestions
# Each entry maps a lowercase skill name to a concrete, actionable resume tip.
# Unmapped skills fall back to a generic "add project" template.
# ---------------------------------------------------------------------------
_SKILL_SUGGESTIONS: dict[str, str] = {
    # Cloud / infrastructure
    "aws": "Add a cloud deployment project (e.g. host a REST API on EC2 or deploy a model on Lambda/SageMaker).",
    "azure": "Add an Azure project — deploy a web app via Azure App Service or set up a CI/CD pipeline with Azure DevOps.",
    "gcp": "Add a GCP project — use BigQuery for data analysis or deploy a containerised app on Cloud Run.",
    "docker": "Add a bullet showing you containerised a project: 'Dockerised [app], reducing environment setup from 30 min to < 1 min.'",
    "kubernetes": "Add a bullet about orchestrating containers: 'Deployed multi-service app on Kubernetes, configuring auto-scaling and health checks.'",
    "terraform": "Add an infrastructure-as-code mini-project: provision a VPC + EC2 instance with Terraform and document it on GitHub.",
    "ci/cd": "Add a GitHub Actions (or Jenkins) pipeline bullet: 'Set up CI/CD pipeline that auto-deploys on push, cutting release time by X%.'",

    # Backend / databases
    "django": "Add a Django CRUD project with user auth — a blog, task manager, or e-commerce MVP works well.",
    "fastapi": "Add a FastAPI REST project: build and document an API with Swagger, include request validation and JWT auth.",
    "flask": "Add a Flask micro-project: a REST endpoint, a web scraper, or a Telegram bot backed by a small DB.",
    "node.js": "Add a Node/Express project — a real-time chat app or REST API with MongoDB is a strong signal.",
    "spring boot": "Add a Spring Boot microservice project with REST endpoints and JPA/Hibernate for persistence.",
    "postgresql": "Mention PostgreSQL by name in an existing project bullet and add a line about schema design or query optimisation.",
    "mysql": "Add a schema design bullet: 'Designed normalised MySQL schema for [app], reducing query time by X%.'",
    "mongodb": "Add a MongoDB project bullet: 'Used MongoDB to store [data type], indexing key fields for sub-10ms reads.'",
    "redis": "Add a caching bullet: 'Integrated Redis caching layer, reducing DB load by X% on high-traffic endpoints.'",
    "kafka": "Add an event-streaming project: build a producer-consumer pipeline using Kafka and write about the throughput achieved.",
    "graphql": "Add a GraphQL API project or convert an existing REST endpoint to GraphQL and describe the query efficiency gain.",

    # Frontend
    "react": "Add a React project (SPA, dashboard, or portfolio) with component breakdown and state management described in bullets.",
    "typescript": "Add a note to an existing JS project: 'Migrated codebase to TypeScript, eliminating X runtime type errors.'",
    "next.js": "Add a Next.js project: an SSR/ISR blog or product page — mention SEO improvements or page-load metrics.",
    "vue": "Add a Vue 3 project with Composition API; describe a component you built and its reuse across the app.",
    "angular": "Add an Angular project bullet mentioning RxJS observables, lazy loading, or form validation.",
    "tailwind css": "Mention Tailwind in existing frontend projects and add 'Implemented responsive UI with Tailwind CSS'.",

    # ML / AI
    "machine learning": "Add an ML project: train a classifier or regression model on a public dataset, report accuracy/F1.",
    "deep learning": "Add a neural-network project: image classification with CNNs or text classification with RNNs — include dataset size and accuracy.",
    "pytorch": "Add a PyTorch project bullet: 'Built [model] in PyTorch, trained on [dataset], achieved [metric].'",
    "tensorflow": "Add a TensorFlow/Keras project: a CNN, LSTM, or transfer-learning experiment with reported metrics.",
    "scikit-learn": "Add a scikit-learn bullet: 'Applied Random Forest / XGBoost to [problem], achieving [accuracy]% on test set.'",
    "nlp": "Add an NLP project: sentiment analysis, named-entity recognition, or a chatbot — mention the library (spaCy/Transformers).",
    "computer vision": "Add a CV project: object detection with YOLO, image segmentation, or OCR — report mAP or accuracy.",
    "langchain": "Add an LLM application project: a RAG pipeline or AI agent using LangChain, describe the use case and model used.",
    "hugging face": "Add a Transformers project: fine-tune a BERT/GPT model on a domain-specific dataset and report eval metrics.",
    "mlflow": "Add a model-tracking bullet: 'Used MLflow to track 30+ experiments, comparing hyperparameters and metrics.'",

    # Data / analytics
    "pandas": "Add a data analysis project: clean and analyse a public dataset (Kaggle works), show insights in a notebook.",
    "numpy": "Add a numerical-computing bullet in an existing ML/data project: 'Used NumPy for vectorised operations, reducing processing time by X%.'",
    "sql": "Add a SQL project or bullet: 'Wrote complex JOIN/window-function queries to extract KPIs from a 1M-row dataset.'",
    "spark": "Add a Spark project: process a large public dataset (NYC taxi, GitHub events) and describe the transformation pipeline.",
    "tableau": "Add a Tableau/Power BI dashboard project: connect to real data, publish to Tableau Public, and link it on your resume.",
    "power bi": "Add a Power BI dashboard project — connect to a dataset, build 3+ visuals, and describe the business insight surfaced.",
    "airflow": "Add a pipeline bullet: 'Orchestrated daily ETL pipeline with Airflow DAGs, processing X records/day reliably.'",

    # DevOps / tools
    "git": "Add 'Version control: Git / GitHub' to your Skills section and mention 'maintained feature branches and PRs' in a project.",
    "linux": "Add a Linux bullet: 'Administered Ubuntu server — set up cron jobs, SSH access, and automated log rotation.'",
    "nginx": "Add a deployment bullet: 'Configured Nginx as a reverse proxy for a Flask/FastAPI app, serving over HTTPS.'",

    # Soft / generic
    "agile": "Add 'Worked in a 2-week Agile sprint cycle, participating in stand-ups and retrospectives' to a team project bullet.",
    "communication": "Add a leadership or presentation bullet: led a team demo, wrote technical documentation, or presented findings.",
}


def _suggest_for_skill(skill: str) -> str:
    """Return a concrete resume improvement suggestion for a missing skill."""
    key = skill.lower().strip()
    if key in _SKILL_SUGGESTIONS:
        return _SKILL_SUGGESTIONS[key]
    # Generic fallback — still actionable, not a no-op
    return (
        f"Add a project or bullet that demonstrates hands-on use of {skill} — "
        "even a small personal project signals genuine familiarity to recruiters."
    )


_ROLE_SIGNALS: dict[str, set[str]] = {
    "ML Engineer": {
        "tensorflow", "pytorch", "keras", "scikit-learn", "scikit", "numpy",
        "pandas", "nlp", "machine learning", "deep learning", "computer vision",
        "opencv", "huggingface", "transformers", "llm", "bert", "spacy",
        "xgboost", "lightgbm", "mlflow", "wandb", "cuda",
    },
    "Backend Engineer": {
        "django", "fastapi", "flask", "spring", "express", "node",
        "postgresql", "mysql", "mongodb", "redis", "docker", "kubernetes",
        "kafka", "rabbitmq", "api", "rest", "grpc", "nginx",
    },
    "Frontend Engineer": {
        "react", "angular", "vue", "svelte", "javascript", "typescript",
        "css", "html", "next.js", "tailwind", "webpack", "vite",
        "redux", "graphql",
    },
    "Data Engineer": {
        "spark", "hadoop", "airflow", "dbt", "kafka", "flink", "etl",
        "bigquery", "redshift", "snowflake", "databricks", "sql",
        "tableau", "power bi", "looker",
    },
}


def _infer_role(detected_skills: list[str]) -> str:
    """Infer the most likely target role from detected skills. Returns '' if unclear."""
    lower = {s.lower() for s in detected_skills}
    best_role, best_count = "", 0
    for role, signals in _ROLE_SIGNALS.items():
        count = len(lower & signals)
        if count > best_count:
            best_count, best_role = count, role
    return best_role if best_count >= 2 else ""


def _build_suggestions(
    data: dict,
    all_bullets: list[str],
    detected_skills: list[str],
    missing_sections: list[str],
) -> list[str]:
    """
    Content-aware suggestions — every item is grounded in the actual resume.
    No generic fallbacks that apply to everyone regardless of their resume.
    """
    suggestions: list[str] = []

    # 1. Quantification: bullets exist but none contain numbers
    if all_bullets:
        has_numbers = any(any(ch.isdigit() for ch in b) for b in all_bullets)
        if not has_numbers:
            suggestions.append(
                "Quantify impact in your bullets — add concrete numbers "
                "(%, ₹, users, ms latency, requests/sec) to make achievements measurable."
            )

    # 2. Action verb coverage
    if all_bullets:
        weak = [
            b for b in all_bullets
            if not b.split() or b.split()[0].lower().strip(".,") not in _ACTION_VERBS
        ]
        if len(weak) > max(1, len(all_bullets) // 2):
            suggestions.append(
                "Start more bullets with strong action verbs (Built, Engineered, "
                "Implemented, Automated, Optimized) — these are the first thing "
                "recruiters and ATS scanners look for."
            )

    # 3. Bullet density — thin sections
    if 0 < len(all_bullets) < 4:
        suggestions.append(
            "Add more detail: aim for 3–5 bullets per role describing what you built, "
            "how (which technologies), and with what measurable result."
        )

    # 4. Missing critical sections — ordered by impact on internship applications
    _SECTION_TIPS = {
        "skills": (
            "Add a dedicated Skills section listing 10+ technical skills — "
            "ATS systems keyword-match before a human ever reads your resume."
        ),
        "projects": (
            "Add a Projects section — for Indian internship applications this is "
            "often weighted above experience, especially for freshers."
        ),
        "education": "Include your Education (degree, institution, CGPA, graduation year).",
        "certifications": (
            "Add certifications (Coursera, NPTEL, AWS, Google) — they signal "
            "self-driven learning and improve keyword coverage."
        ),
        "email": "Add a professional email address to your contact header.",
        "phone": "Add a phone number — recruiters call first, then email.",
    }
    for code in ["skills", "projects", "education", "certifications", "email", "phone"]:
        if code in missing_sections and code in _SECTION_TIPS:
            suggestions.append(_SECTION_TIPS[code])
            if len(suggestions) >= 4:
                break

    # 5. Skill count — only if section exists but count is low
    skill_count = len(detected_skills)
    if skill_count < 6 and "skills" not in missing_sections:
        suggestions.append(
            f"Only {skill_count} skills detected. Expand to 10+ — list frameworks, "
            "databases, cloud tools, and languages you've actually used."
        )

    # 6. True catch-all — only when everything is genuinely strong
    if not suggestions:
        suggestions.append(
            "Strong profile! Next level: add specific outcomes (users served, "
            "latency reduced, accuracy improved) to every experience bullet."
        )

    return suggestions[:5]


@router.get("/resume/{resume_id}/analysis")
async def get_resume_analysis(
    resume_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    analysis = (
        db.query(ResumeAnalysis)
        .filter(ResumeAnalysis.resume_id == resume_id, ResumeAnalysis.user_id == user.id)
        .order_by(ResumeAnalysis.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    return {
        "id": analysis.id,
        "resume_id": str(analysis.resume_id),
        "ats_score": analysis.ats_score,
        "extracted_skills": analysis.extracted_skills or [],
        "missing_sections": analysis.missing_sections or [],
        "analysis": analysis.analysis_json or {},
        "created_at": analysis.created_at,
    }


@router.post("/resume/optimize")
async def optimize_resume(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Resume Improver — assembles three sections from the user's REAL parsed resume:

      * improvements      : ONLY genuinely-missing sections (from the analyzer's
                            missing_sections) plus a targeted quantify tip
      * missing_keywords  : aggregated stored semantic missing-skills across the
                            user's top recommendations (same source as skill-gap)
      * improved_bullets  : Groq rewrites of the REAL Experience/Project bullets
                            parsed from the resume (before -> after)

    Bullets are read from the stored resume analysis (analysis_json), NOT the
    builder-only experiences/projects tables (which are empty for uploads).
    No mock data.
    """
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume found. Upload a resume first.",
        )

    # Latest parsed analysis holds the section line-lists (experience/projects/...).
    analysis = (
        db.query(ResumeAnalysis)
        .filter(ResumeAnalysis.user_id == user.id)
        .order_by(ResumeAnalysis.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not analyzed yet. Re-upload your resume and try again.",
        )

    data = analysis.analysis_json or {}
    missing_sections = analysis.missing_sections or data.get("missing_sections", []) or []
    detected_skills: list[str] = analysis.extracted_skills or []

    # ── Infer target role from detected skills (drives LLM context + filtering) ──
    role_context = (data.get("career_interests") or "").strip()
    if not role_context:
        role_context = _infer_role(detected_skills)

    # ---- C) Extract real bullets from the parsed Experience/Projects sections ----
    experience_bullets = _extract_bullets(data.get("experience", []) or [])
    project_bullets = _extract_bullets(data.get("projects", []) or [])
    all_bullets = experience_bullets + project_bullets

    optimizer = ResumeOptimizer(db)

    # Normalize spacing/hyphenation on each bullet before the LLM sees it. This
    # protects resumes analyzed BEFORE the extraction fix (whose stored text may
    # still be merged) so we never send "ImplementedstrictDomain-Driven..." to Groq.
    from app.services.text_normalizer import normalize_resume_text

    improved_bullets = []
    for raw_bullet in all_bullets[:MAX_BULLETS_TO_IMPROVE]:
        bullet = normalize_resume_text(raw_bullet).strip()
        if is_strong_bullet(bullet):
            # No-change logic: already strong (action verb + quantified + tech).
            # Python skips the LLM; both sides of the pair are the same text.
            improved = bullet
        else:
            improved = optimizer.optimize_bullet(bullet, role_context)
            improved = (improved or bullet).strip()
            # Guard: if the LLM somehow returned identical text (fallback path),
            # the pair is still included — the frontend "Before / After" shows it
            # honestly rather than hiding the entry.
        improved_bullets.append({
            "original": bullet,
            "improved": improved,
        })

    # ---- A) Suggested improvements — content-aware, not generic ----------------
    improvements = _build_suggestions(data, all_bullets, detected_skills, missing_sections)

    # ---- B) Missing keywords — role-relevant, excluding already-known skills ----
    # Only pull from recommendations that are a reasonable role fit (≥55 %).
    # This filters out poor-match internships whose missing skills (e.g. Angular
    # for a backend-focused candidate) would otherwise pollute the keyword list.
    detected_lower = {s.lower() for s in detected_skills}
    recs = (
        db.query(Recommendation)
        .filter(
            Recommendation.user_id == user.id,
            Recommendation.match_percentage >= 55,
        )
        .order_by(Recommendation.match_percentage.desc())
        .limit(20)
        .all()
    )
    missing_counter: Counter = Counter()
    for rec in recs:
        for skill in (rec.missing_skills or []):
            # Skip anything the user already has on their resume.
            if skill.lower() not in detected_lower:
                missing_counter[skill] += 1

    # Fall back to ALL recs (no threshold) if the filtered set is too sparse.
    if len(missing_counter) < 3:
        for rec in db.query(Recommendation).filter(Recommendation.user_id == user.id).all():
            for skill in (rec.missing_skills or []):
                if skill.lower() not in detected_lower:
                    missing_counter[skill] += 1

    missing_keywords = [skill for skill, _ in missing_counter.most_common(MAX_MISSING_KEYWORDS)]

    # ---- D) Per-skill resume suggestions — one concrete action per missing skill ----
    skill_suggestions = [
        {"skill": skill, "suggestion": _suggest_for_skill(skill)}
        for skill in missing_keywords[:MAX_SKILL_SUGGESTIONS]
    ]

    return {
        "improvements": improvements,
        "missing_keywords": missing_keywords,
        "improved_bullets": improved_bullets,
        "skill_suggestions": skill_suggestions,
    }


def _coerce_str(val) -> str:
    return str(val).strip() if val else ""


# ---------------------------------------------------------------------------
# NEW: Role-aware career intelligence endpoint
# ---------------------------------------------------------------------------

@router.post("/resume/career-analysis")
async def career_analysis(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Run role-aware career analysis on the user's most recent resume.

    Returns structured JSON with:
      - inferred target role + confidence
      - match score for that role
      - present and missing skills (role-specific)
      - per-skill "how to build" guidance
      - mentor-style career guidance paragraph
      - resume improvement suggestions

    Backed by Groq LLaMA 70B. Falls back gracefully on LLM failure.
    Never touches existing /resume/optimize or /resume/{id}/analysis routes.
    """
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    # Require an uploaded resume
    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume found. Upload a resume first.",
        )

    # Get latest parsed analysis to extract raw resume text from sections
    analysis = (
        db.query(ResumeAnalysis)
        .filter(ResumeAnalysis.user_id == user.id)
        .order_by(ResumeAnalysis.created_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not analyzed yet. Re-upload your resume and try again.",
        )

    # Reconstruct readable resume text from stored analysis sections.
    # This is cleaner than raw PDF text — already section-extracted.
    data = analysis.analysis_json or {}
    from app.services.text_normalizer import normalize_resume_text

    def _join(section: list | None) -> str:
        return "\n".join(normalize_resume_text(str(line)) for line in (section or []) if line)

    name    = _coerce_str(data.get("name"))
    email   = _coerce_str(data.get("email"))
    phone   = _coerce_str(data.get("phone"))
    skills  = analysis.extracted_skills or []

    resume_text_parts = []
    if name:
        resume_text_parts.append(f"Name: {name}")
    if email:
        resume_text_parts.append(f"Email: {email}")
    if phone:
        resume_text_parts.append(f"Phone: {phone}")
    if skills:
        resume_text_parts.append(f"Skills: {', '.join(skills)}")
    education_text = _join(data.get("education"))
    if education_text:
        resume_text_parts.append(f"Education:\n{education_text}")
    experience_text = _join(data.get("experience"))
    if experience_text:
        resume_text_parts.append(f"Experience:\n{experience_text}")
    projects_text = _join(data.get("projects"))
    if projects_text:
        resume_text_parts.append(f"Projects:\n{projects_text}")
    certs_text = _join(data.get("certifications"))
    if certs_text:
        resume_text_parts.append(f"Certifications:\n{certs_text}")

    resume_text = "\n\n".join(resume_text_parts)

    from app.services.career_analysis_service import analyse_career
    result = analyse_career(resume_text)

    # Tag fallback so the frontend can show a gentle "try again" message
    # without crashing on missing fields — but still return 200.
    return result
