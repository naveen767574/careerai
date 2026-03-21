# Backend Implementation Guide
## AI-Powered Internship & Career Recommendation System

> Phase-by-phase backend development reference.
> Framework: FastAPI · Python 3.11 · SQLAlchemy · Alembic · PostgreSQL

---

## Phase 0 — Project Foundation

### Goals
- Initialize FastAPI project structure
- Configure PostgreSQL connection
- Set up Alembic migrations
- Implement JWT authentication
- Configure middleware (CORS, rate limiting, logging, error handling)

### Project Structure to Create

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry, CORS, middleware registration
│   ├── database.py          # Engine, SessionLocal, Base, get_db dependency
│   ├── config.py            # Settings from environment variables
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py          # Users and password_reset_tokens tables
│   ├── routes/
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── auth_service.py
│   └── utils/
│       ├── __init__.py
│       ├── hashing.py       # bcrypt helpers
│       ├── jwt.py           # JWT creation and validation
│       └── logger.py        # Structured JSON logging
├── migrations/              # Alembic migrations folder
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py
│   └── unit/
├── requirements.txt
├── alembic.ini
├── render.yaml
└── .env.example
```

### `requirements.txt` — Phase 0

```
fastapi==0.111.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.30
alembic==1.13.1
psycopg2-binary==2.9.9
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
python-dotenv==1.0.1
pydantic-settings==2.2.1
```

### `app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth
from app.utils.logger import setup_logging

setup_logging()
app = FastAPI(title="AI Career Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
```

### Authentication System

**Key methods:**
```python
class AuthService:
    def register_user(email: str, password: str, name: str) -> User
    def login_user(email: str, password: str) -> dict    # {"access_token": ..., "token_type": "bearer"}
    def verify_token(token: str) -> User
    def hash_password(password: str) -> str               # bcrypt, rounds=12
    def verify_password(plain: str, hashed: str) -> bool
    def generate_reset_token(email: str) -> str           # 1h expiration
    def validate_reset_token(token: str) -> User
```

**Security constants:**
- JWT algorithm: HS256
- JWT expiration: 24 hours
- bcrypt salt rounds: 12
- Password reset token: 1 hour expiration

### Middleware to Configure

```python
# Rate limiting
@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    # 10/min unauthenticated, 100/min authenticated
    # Return HTTP 429 with retry-after header when exceeded

# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    # Log full stack trace; return generic 500 without exposing internals

# Structured logging
# JSON format: timestamp, level, user_id, endpoint, duration, status_code
```

### Auth Endpoints

| Method | Endpoint | Body | Response |
|---|---|---|---|
| POST | `/api/auth/register` | `{email, password, name}` | `{user_id, email, name}` 201 |
| POST | `/api/auth/login` | `{email, password}` | `{access_token, token_type, user}` 200 |
| GET | `/api/auth/me` | — | `{user_id, email, name}` 200 |
| POST | `/api/auth/request-reset` | `{email}` | `{message}` 200 |
| POST | `/api/auth/reset-password` | `{token, new_password}` | `{message}` 200 |

### Phase 0 Checklist

- [ ] FastAPI app initializes and `/health` returns 200
- [ ] PostgreSQL connection established
- [ ] Alembic initial migration runs (`alembic upgrade head`)
- [ ] `users` and `password_reset_tokens` tables created
- [ ] Register endpoint creates user with hashed password
- [ ] Login returns valid JWT
- [ ] Protected routes reject invalid/expired tokens with 401
- [ ] Rate limiting returns 429 when exceeded
- [ ] CORS rejects requests from non-frontend origins
- [ ] Structured JSON logging working
- [ ] Unit tests passing for auth service

---

## Phase 1 — Resume Upload & Storage

### Goals

- Accept PDF and DOCX file uploads (max 10MB)
- Store files in Cloudflare R2
- Create resume record in database
- One resume per user (replace on re-upload)

### Dependencies to Add

```
boto3==1.34.0          # R2 / S3-compatible storage
python-magic==0.4.27   # File type validation
```

### New Models

```python
# models/resume.py
class Resume(Base):
    __tablename__ = "resumes"
    id, user_id, file_name, file_path, file_type, file_size
    uploaded_at, analyzed, score, feedback
```

### ResumeUploadService

```python
class ResumeUploadService:
    def validate_file(file: UploadFile) -> None          # Check type + size
    def upload_to_r2(file: UploadFile, user_id: int) -> str  # Returns R2 path
    def create_or_replace_resume(user_id: int, ...) -> Resume
    def delete_resume(user_id: int) -> None
    def get_signed_url(file_path: str) -> str            # Temp access URL
```

### Resume Endpoints — Phase 1

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/resumes/upload` | Upload file; triggers async analysis |
| GET | `/api/resumes/me` | Get resume metadata + score |
| DELETE | `/api/resumes/me` | Delete resume + R2 file |

### Phase 1 Checklist

- [ ] PDF/DOCX files accepted; other types return 400
- [ ] Files over 10MB return 413
- [ ] File stored in R2 at `resumes/{user_id}/{filename}`
- [ ] Resume record created in DB with metadata
- [ ] Re-upload replaces previous resume (UNIQUE user_id constraint)
- [ ] Signed URL generated for secure access
- [ ] Delete removes both DB record and R2 file

---

## Phase 2 — Resume Analysis (NLP)

### Goals

- Parse uploaded resume using spaCy
- Extract: contact info, education, experience, projects, skills
- Calculate resume score (0–100)
- Store all extracted data in DB
- Trigger automatically after upload (background task)

### Dependencies to Add

```
spacy==3.7.4
PyPDF2==3.0.1
python-docx==1.1.0
scikit-learn==1.4.2    # For TF-IDF (also needed for Recommendation Engine)
```

```bash
python -m spacy download en_core_web_sm
```

### New Models

```python
# models/resume.py additions
class ResumeData(Base):   # contact info
class Education(Base)
class Experience(Base)
class Project(Base)
class Skill(Base)         # skill_name, skill_type
```

### ResumeAnalyzer

```python
class ResumeAnalyzer:
    def extract_text(file_path: str, file_type: str) -> str
    def parse_contact_info(text: str) -> ContactInfo     # NER + Regex
    def parse_education(text: str) -> list[Education]    # Pattern matching
    def parse_experience(text: str) -> list[Experience]
    def parse_projects(text: str) -> list[Project]       # Section detection
    def extract_skills(text: str) -> list[Skill]         # NER + keyword list
    def normalize_skill(skill: str) -> str               # "javascript" → "JavaScript"
    def calculate_score(resume_data: dict) -> tuple[int, list[str]]
```

### Scoring Breakdown

| Component | Max Points |
|---|---|
| Sections present (contact, education, experience, skills) | 40 |
| Skill diversity (1pt per unique skill, max 30) | 30 |
| Experience completeness (5pt per entry) | 15 |
| Education completeness | 10 |
| Projects (1pt per project, max 5) | 5 |
| **Total** | **100** |

### Analysis Endpoint

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/resumes/analysis` | Full analysis: score, breakdown, suggestions |

### Phase 2 Checklist

- [ ] Text extracted from both PDF and DOCX
- [ ] spaCy pipeline processes text
- [ ] Contact info (name, email, phone) extracted
- [ ] Education entries extracted and stored
- [ ] Experience entries extracted and stored
- [ ] Skills extracted, normalized, and stored
- [ ] Score calculated and stored on resume record
- [ ] Analysis runs as background task after upload
- [ ] `RESUME_ANALYZED` notification created on completion

---

## Phase 3 — Web Scraper (Scout Foundation)

### Goals

- Scrape internship listings from LinkedIn, Indeed, Naukri, Internshala
- Deduplicate using SHA256 hash
- Run on 6-hour cron schedule
- Store listings with required skills extracted via NLP

### Dependencies to Add

```
beautifulsoup4==4.12.3
requests==2.31.0
fake-useragent==1.4.0   # User-agent rotation
```

### Scraper Structure

```
app/
└── scraper/
    ├── __init__.py
    ├── run.py              # Entry point for cron job
    ├── orchestrator.py     # Manages all sources in parallel
    ├── sources/
    │   ├── linkedin.py
    │   ├── indeed.py
    │   ├── naukri.py
    │   └── internshala.py
    └── utils/
        ├── deduplicator.py  # SHA256 hash comparison
        └── extractor.py     # NLP skill extraction from description
```

### Key Methods

```python
class WebScraper:
    def scrape_all_sources() -> list[Internship]
    def detect_duplicate(internship: Internship) -> bool
    def generate_hash(title, company, location) -> str  # SHA256
    def update_or_create(internship: Internship) -> Internship
    def respect_rate_limits(source: str) -> None        # 1 req/2 sec per source
```

### Error Handling

| Error | Behavior |
|---|---|
| Network error | Retry 3x with exponential backoff |
| Parsing error | Log, skip listing, continue |
| 429 from source | Wait specified time, retry |
| Source unavailable | Log, continue with other sources |

### Phase 3 Checklist

- [ ] All 4 sources scraped on cron trigger
- [ ] Rate limiting: min 2s between requests per source
- [ ] Duplicate detection working (SHA256 hash)
- [ ] New listings inserted; duplicates updated
- [ ] Required skills extracted from description via NLP
- [ ] `internship_skills` table populated
- [ ] Cron job configured in `render.yaml`
- [ ] Errors logged without stopping other sources

---

## Phase 4 — Recommendation Engine

### Goals

- TF-IDF vectorization of user skills vs. internship requirements
- Cosine similarity matching
- Filter threshold ≥ 0.3, return top 20
- Store results in `recommendations` table

### RecommendationEngine

```python
class RecommendationEngine:
    def get_recommendations(user_id: int, limit: int = 20) -> list[InternshipRecommendation]
    def vectorize_user_profile(user_id: int) -> np.ndarray
    def vectorize_internships(internship_ids: list[int]) -> np.ndarray
    def calculate_similarity(user_vector, internship_vectors) -> np.ndarray
    def filter_by_threshold(recs: list, threshold: float = 0.3) -> list

# TF-IDF config:
TfidfVectorizer(max_features=500, ngram_range=(1,2), stop_words='english', lowercase=True)
```

### Match Quality

| Score | Label |
|---|---|
| ≥ 0.7 | Excellent |
| 0.5–0.7 | Good |
| 0.3–0.5 | Fair |
| < 0.3 | Filtered |

### Recommendation Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/recommendations` | Top 20 matches |
| POST | `/api/recommendations/refresh` | Regenerate |

### Phase 4 Checklist

- [ ] TF-IDF vectors built from user skills and internship requirements
- [ ] Cosine similarity calculated correctly
- [ ] Scores below 0.3 filtered out
- [ ] Results sorted descending, capped at top 20
- [ ] Matched and missing skills computed per recommendation
- [ ] Results stored in `recommendations` table
- [ ] Recommendations regenerated after each scrape run

---

## Phase 5 — Career Tools

### Goals

- Career Path Predictor: returns 3–5 paths ranked by alignment score
- Role Comparator: side-by-side skill comparison for 2–4 roles

### CareerPathPredictor

```python
class CareerPathPredictor:
    def generate_paths(profile: ProfileAnalysis) -> list[CareerPath]  # 3-5 paths
    def rank_paths(paths, profile) -> list[CareerPath]                 # By alignment_score
    def estimate_timeline(path, current_level) -> str                  # Entry/Mid/Senior
```

### RoleComparator

```python
class RoleComparator:
    def compare_roles(internship_ids: list[int], user_id: int) -> RoleComparison
    # Accepts 2-4 IDs; returns common skills, unique skills per role, match % per role
```

### Career Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/career/paths` | 3–5 career paths |
| POST | `/api/career/compare` | Compare roles |
| GET | `/api/internships/:id/skill-gap` | User vs. listing skill gap |

---

## Phase 6 — Application Tracking

### Goals

- Track applications with statuses
- Notes per application
- CRUD operations

### Application Statuses

`APPLIED` → `INTERVIEW_SCHEDULED` → `ACCEPTED` or `REJECTED`

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/applications` | Create (status: APPLIED) |
| GET | `/api/applications` | List (filterable by status) |
| PATCH | `/api/applications/:id` | Update status or notes |
| DELETE | `/api/applications/:id` | Remove |

---

## Phase 7 — Agent Infrastructure

### Goals

- Create `agent_state` and `agent_runs` tables
- Build Orchestrator skeleton
- Wire Scout (scraper elevated to agent with LLM reasoning)
- Wire Analyst (weekly skill snapshots + trend detection)

### New Dependencies

```
openai==1.30.0
celery==5.4.0       # Optional: for background task queue
redis==5.0.4        # Optional: Celery broker
```

### Orchestrator Loop

```python
# app/orchestrator/runner.py
def orchestrator_loop(user_id: int, trigger: str):
    state = load_agent_state(user_id)
    while not state["done"]:
        thought = llm.reason(state, trigger)
        action  = llm.decide_action(thought)
        result  = dispatch_agent(action, state)
        state   = update_state(state, result)
        persist_agent_state(user_id, state)
        log_agent_run(user_id, action, result)
```

### Agent Control Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/agent/trigger` | Manual trigger |
| GET | `/api/agent/status` | Current state |
| GET | `/api/agent/runs` | Run history |
| GET | `/api/agent/runs/:id` | Run detail |

---

## Phase 8 — Writer Agent

### Goals

- Draft cover letters per listing + user profile
- Store drafts with approval workflow

### WriterAgent

```python
class WriterAgent:
    def draft_cover_letter(user_id: int, internship_id: int) -> CoverLetterDraft
    # Reads: resume data + internship details + match rationale
    # LLM constructs grounded, non-template output
    # Stores in cover_letter_drafts with status='draft'
```

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/drafts` | All drafts |
| POST | `/api/drafts/generate` | Trigger Writer for listing |
| PATCH | `/api/drafts/:id` | Edit draft |
| PATCH | `/api/drafts/:id/approve` | Mark approved |
| DELETE | `/api/drafts/:id` | Discard |

---

## Phase 9 — Coach Agent + Bolt AI

### Goals

- Coach generates proactive briefings from Scout + Analyst output
- Bolt AI chat with 5 intent modes, reads Coach brief as context

### CoachAgent

```python
class CoachAgent:
    def generate_brief(user_id: int) -> CoachingBrief
    # Detects inactivity: no applications in 5+ days
    # Reads top Scout matches + Analyst trend report
    # Generates coaching_brief stored in DB
```

### BoltAIAssistant

```python
class BoltAIAssistant:
    def process_message(user_id, message, session_id) -> BoltResponse
    def classify_intent(message) -> str  # 5 modes
    # Rate limit: 20 req/min; all logged to chat_logs; 90-day retention
```

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/coach/brief` | Latest brief |
| GET | `/api/coach/history` | Past briefs |
| POST | `/api/bolt/chat` | Chat message |
| GET | `/api/bolt/history` | Session history |
| DELETE | `/api/bolt/history/:id` | Delete session |

---

## Phase 10 — Builder Agent

### Goals

- 12-step conversational resume creation
- Jinja2 template rendering
- LLM optimization + ATS scoring
- PDF (WeasyPrint) and DOCX (python-docx) export
- Post-build pipeline: auto-trigger Resume Analyzer + Orchestrator

### Dependencies to Add

```
jinja2==3.1.4
weasyprint==62.3
python-docx==1.1.0    # Already added in Phase 2
```

### Key Classes

```python
class ResumeBuilderService:
    def start_session(user_id) -> BuilderSession         # Returns step 1 question
    def process_answer(session_id, message) -> BuilderResponse
    def finalize_resume(session_id) -> ResumeData
    def trigger_post_build_pipeline(user_id, resume_data)  # → Analyzer + Orchestrator

class TemplateEngine:
    def recommend_templates(resume_data) -> list[TemplateRecommendation]
    def render_template(template_name, resume_data) -> str  # HTML string

class ResumeOptimizer:
    def optimize_bullet(raw_text, role_context) -> str
    def calculate_ats_score(resume_data) -> ATSScore     # Structure+Keywords+Completeness

class ExportService:
    def export_pdf(rendered_html, output_path) -> str    # WeasyPrint
    def export_docx(resume_data, output_path) -> str     # python-docx
```

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/resume-agent/start-session` | Start builder |
| POST | `/api/resume-agent/answer` | Submit answer |
| GET | `/api/resume-agent/preview/:id` | HTML preview |
| POST | `/api/resume-agent/optimize` | LLM optimization |
| GET | `/api/resume-agent/ats-score/:id` | ATS score |
| POST | `/api/resume-agent/finalize` | Finalize + pipeline |
| POST | `/api/resume-agent/export-pdf` | PDF download |
| POST | `/api/resume-agent/export-docx` | DOCX download |
| GET | `/api/resume-agent/versions` | Version history |

---

## Phase 11 — Interview Agent

### Goals

- Generate 10 role-specific questions per listing
- Evaluate answers with LLM (score 0–10 per answer)
- Produce structured feedback report

### Key Classes

```python
class QuestionGenerator:
    def generate_question_set(job_listing, user_profile) -> list[InterviewQuestion]
    def detect_role_category(job_title, skills) -> str

class AnswerEvaluator:
    def evaluate_answer(question, answer, context) -> AnswerEvaluation
    # Returns: score(0-10), verdict, strengths, weaknesses, model_answer, improvement_tip

class FeedbackReporter:
    def compile_report(session, evaluations) -> InterviewFeedbackReport
    # overall_score, readiness_level, top_strengths, top_improvements, resources
```

### Readiness Levels

| Score | Level |
|---|---|
| ≥ 75 | Ready |
| 55–74 | Almost Ready |
| < 55 | Needs Prep |

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/interview/start` | Start, get first question |
| POST | `/api/interview/answer` | Submit, get next |
| POST | `/api/interview/complete` | Evaluate + report |
| GET | `/api/interview/report/:id` | Full report |
| GET | `/api/interview/history` | Past sessions |

---

## Phase 12 — LinkedIn Agent

### Goals

- Accept LinkedIn sections as text input
- Gap analysis: resume data (DB) vs. LinkedIn text (user-pasted)
- Generate 3 headline variants, about section, bullet improvements, skill reorder
- Profile completeness score (0–100)

### Key Classes

```python
class GapAnalyzer:
    def analyze(profile_input, resume_data, skill_trends) -> ProfileGapReport
    def find_missing_skills(linkedin_skills, resume_skills) -> list[str]
    def assess_headline_strength(headline, target_roles) -> HeadlineAssessment

class ContentOptimizer:
    def rewrite_headline(current, resume_data, target_roles) -> list[HeadlineVariant]
    def write_about_section(resume_data, target_roles, current_about) -> str
    def enhance_experience_bullets(bullets, resume_experience) -> list[BulletImprovement]

class ProfileScorer:
    def calculate_score(profile_input, resume_data) -> ProfileScore
    # Headline(20) + About(20) + Experience(20) + Skills(15) + Projects(10) + Education(10) + Photo(5)
```

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/linkedin/analyze` | Submit profile, trigger analysis |
| GET | `/api/linkedin/report/:id` | Optimization report |
| POST | `/api/linkedin/regenerate` | Regenerate section with feedback |
| GET | `/api/linkedin/score/:id` | Score breakdown |

---

## Phase 13 — Notification System

### Goals

- Daily email digest (1 email/user/day max)
- In-app notifications for all event types
- All new notification types for agents

### Notification Types

```python
NOTIFICATION_TYPES = [
    "NEW_RECOMMENDATIONS",    # Post-Scout new matches
    "APPLICATION_UPDATE",     # Status change
    "RESUME_ANALYZED",        # Analysis complete
    "INTERVIEW_REPORT_READY", # Interview evaluation done
    "LINKEDIN_REPORT_READY",  # LinkedIn analysis done
    "COACHING_BRIEF",         # Coach Agent new brief
    "SYSTEM_UPDATE",          # Announcements
]
```

### Dependencies

```
emails==0.6           # Email sending
jinja2==3.1.4         # Email templates (already added)
```

---

## Final Requirements File

```
# Core
fastapi==0.111.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.30
alembic==1.13.1
psycopg2-binary==2.9.9

# Auth
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# NLP / ML
spacy==3.7.4
scikit-learn==1.4.2
PyPDF2==3.0.1
python-docx==1.1.0
numpy==1.26.4

# AI
openai==1.30.0

# Scraping
beautifulsoup4==4.12.3
requests==2.31.0
fake-useragent==1.4.0

# File handling
boto3==1.34.0
python-multipart==0.0.9
python-magic==0.4.27

# Resume generation
jinja2==3.1.4
weasyprint==62.3

# Config
pydantic-settings==2.2.1
python-dotenv==1.0.1

# Email
emails==0.6

# Utils
uuid==1.30
```
