# AI-Powered Internship & Career Recommendation System
## Complete Project Documentation

> **Version**: 1.0 — Final
> **Status**: Documentation Complete — Ready to Build
> **Agents**: 7 Specialized Agents + 1 Orchestrator
> **Stack**: FastAPI · React · PostgreSQL · OpenAI GPT-4 · spaCy · scikit-learn

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Agent System](#3-agent-system)
4. [Database Schema](#4-database-schema)
5. [Backend Design](#5-backend-design)
6. [AI & ML Modules](#6-ai--ml-modules)
7. [API Reference](#7-api-reference)
8. [Frontend Design](#8-frontend-design)
9. [Notification System](#9-notification-system)
10. [Testing Strategy](#10-testing-strategy)
11. [Deployment](#11-deployment)
12. [Build Phases](#12-build-phases)
13. [Document Index](#13-document-index)

---

## 1. Project Overview

### What This System Is

A **multi-agent career automation system** with a full-stack web interface. The system does not wait for users to ask questions — it autonomously monitors opportunities, analyzes profiles, tracks skill gaps over time, drafts application materials, prepares users for interviews, and optimizes their LinkedIn presence.

This is not a chatbot with a job board attached. It is an agent system that happens to have a web interface.

### Target Users

Students and early-career professionals who want AI-driven help finding internships, building resumes, and accelerating their careers.

### Technology Stack

| Layer | Technologies |
|---|---|
| Backend | FastAPI, Python 3.11, SQLAlchemy, Alembic, JWT, bcrypt, Uvicorn |
| Frontend | React, TypeScript, Tailwind CSS, Axios, React Router, Vite |
| AI / ML | spaCy (en_core_web_sm), scikit-learn (TF-IDF + Cosine), OpenAI GPT-4 |
| Scraping | BeautifulSoup4, requests |
| Database | PostgreSQL 15+ |
| Deployment | Vercel (frontend), Render/Railway (backend), Supabase/Neon (database) |
| File Storage | Cloudflare R2 |
| Templates | Jinja2 (resume templates) |
| Export | WeasyPrint (PDF), python-docx (DOCX) |

### Core Value Propositions

| Feature | What It Solves |
|---|---|
| Scout Agent | Never miss a relevant listing — autonomous monitoring every 6h |
| Analyst Agent | Know which skills are trending for your specific targets, over time |
| Coach Agent | A proactive mentor that tells you what to do next without being asked |
| Writer Agent | Cover letters that reference your actual experience, not templates |
| Builder Agent | Zero-to-resume in a conversation — solves the blank page problem |
| Interview Agent | Role-specific mock interview practice with real feedback |
| LinkedIn Agent | Profile gap analysis and ready-to-copy rewrites in minutes |

---

## 2. System Architecture

### High-Level Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              Web Interface (React)                            │
│  Dashboard │ Resume │ Builder │ Listings │ Applications │ Skills │ Interview │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │ HTTPS / REST API
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            FastAPI Backend                                    │
│          Auth │ Rate Limiting │ Middleware │ REST Endpoints                   │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          Orchestrator Agent                                   │
│   Trigger: cron / user action / DB event                                     │
│   Loop: Observe → Reason (LLM) → Act (invoke agent) → Update State           │
└───┬──────────┬──────────────┬──────────────┬──────────────┬──────────┬───────┘
    │          │              │              │              │          │
    ▼          ▼              ▼              ▼              ▼          ▼
┌───────┐ ┌────────┐ ┌──────────┐ ┌───────────┐ ┌───────┐ ┌────────┐ ┌────────┐
│Scout  │ │Analyst │ │  Coach   │ │  Writer   │ │Builder│ │Intervw │ │LinkedIn│
│Agent  │ │Agent   │ │  Agent   │ │  Agent    │ │Agent  │ │Agent   │ │Agent   │
└───────┘ └────────┘ └──────────┘ └───────────┘ └───────┘ └────────┘ └────────┘
```

### Three-Tier Architecture

```
┌──────────────────────────────┐
│        Frontend (React)      │  Vercel CDN
│  Pages · Bolt Widget · API   │
└──────────────────────────────┘
              │ HTTPS
              ▼
┌──────────────────────────────┐
│       Backend (FastAPI)      │  Render / Railway
│  Auth · Services · Agents    │
└──────────────────────────────┘
              │ SQL (SSL)
              ▼
┌──────────────────────────────┐
│    Database (PostgreSQL)     │  Supabase / Neon
│    25 Tables · Alembic       │
└──────────────────────────────┘
```

### Security Architecture

| Concern | Implementation |
|---|---|
| Authentication | JWT tokens, 24h expiration, HS256 algorithm |
| Password hashing | bcrypt, salt rounds = 12 |
| Rate limiting | 10/min unauthenticated, 100/min authenticated |
| CORS | Restricted to frontend domain only |
| File storage | Signed URLs, S3-compatible Cloudflare R2 |
| Secrets | Environment variables only, never hardcoded |
| Frontend | JWT in memory only (not localStorage), CSP headers |

---

## 3. Agent System

### Agent Roster

| Agent | Module | Trigger | Real-World Value |
|---|---|---|---|
| Orchestrator | `app/orchestrator/` | Cron / events / user actions | Coordinates all agents in sequence |
| Scout | `app/scout_agent/` | Every 6h + on-demand | Autonomous job discovery + scoring |
| Analyst | `app/analyst_agent/` | Post-Scout + weekly | Skill trend tracking over time |
| Coach | `app/coach_agent/` | Post-Analyst + on login | Proactive career nudges and briefs |
| Writer | `app/writer_agent/` | Per listing / on-demand | Tailored cover letter drafting |
| Builder | `app/resume_agent/` | User selection | Zero-to-resume conversational flow |
| Interview | `app/interview_agent/` | Per application / on-demand | Role-specific mock interview + feedback |
| LinkedIn | `app/linkedin_agent/` | On-demand + Coach nudge | Profile gap analysis + copy rewrites |

### Orchestrator Pattern

```python
def orchestrator_loop(user_id: int, trigger: str):
    state = load_agent_state(user_id)
    while not state["done"]:
        thought = llm.reason(state, trigger)       # What needs to happen?
        action  = llm.decide_action(thought)       # Which agent to call?
        result  = dispatch_agent(action, state)    # Run that agent
        state   = update_state(state, result)      # Update shared state
        persist_agent_state(user_id, state)
```

### Agent Communication

Agents do not call each other directly. All communication flows through the Orchestrator via shared `agent_state` and the `agent_runs` audit table.

```
Orchestrator
  ├── dispatches ──► Scout      → writes output to agent_runs
  ├── reads output → dispatches ──► Analyst  (with Scout output as input)
  ├── reads output → dispatches ──► Coach    (with Analyst output as input)
  ├── dispatches ──► Writer     (on user request or top match trigger)
  ├── dispatches ──► Builder    (on user selection — resume creation)
  ├── dispatches ──► Interview  (on user request per listing)
  └── dispatches ──► LinkedIn   (on user request or Coach nudge)
```

### Scout Agent

- **Purpose**: Discover, score, and rank new internship listings per user
- **Tools**: `scrape_linkedin`, `scrape_indeed`, `scrape_naukri`, `scrape_internshala`, `score_listing_against_profile`, `detect_duplicate`, `upsert_internship`
- **LLM role**: Reasons about fit ("Is this listing worth surfacing for this user? Why?"), goes beyond cosine similarity
- **Output**: Ranked listings with match rationale stored in DB; top matches passed to Orchestrator

### Analyst Agent

- **Purpose**: Track skill gap evolution over time; detect trending skills in the user's target market
- **Tools**: `get_user_skills`, `get_skill_frequency_over_time`, `compare_to_previous_snapshot`, `generate_skill_trend_report`, `update_skill_snapshot`
- **LLM role**: Interprets frequency delta data and generates natural language insights (e.g. "Docker up 28% this month")
- **Output**: Skill trend report + weekly snapshot stored in DB; key insights passed to Coach

### Coach Agent

- **Purpose**: Proactively surface insights and nudges without the user asking
- **Tools**: `get_analyst_report`, `get_scout_top_matches`, `get_application_activity`, `get_user_career_paths`, `generate_coaching_brief`
- **LLM role**: Synthesizes Scout + Analyst outputs into actionable, personalized coaching briefs
- **Output**: Brief stored in DB; delivered as notification + email; powers Bolt chat context

**Example proactive outputs:**
- "You haven't applied in 5 days. Scout found 3 strong matches yesterday."
- "You're 2 skills away from Senior Frontend roles: TypeScript and Docker."
- "Your LinkedIn score is 34/100 — optimizing it could double recruiter visibility."

### Writer Agent

- **Purpose**: Draft tailored cover letters for specific job listings
- **Tools**: `get_resume_data`, `get_internship_details`, `get_match_rationale`, `draft_cover_letter`, `save_draft`
- **LLM role**: Reads structured resume data + listing, reasons about alignment, writes non-generic output
- **Output**: Draft stored with `status: draft`; user reviews and approves in UI

### Builder Agent — Full Spec: `resume_builder_agent.md`

**12-step conversation flow:**

| Step | Phase | Content |
|---|---|---|
| 1 | Personal Info | Name, email, phone, LinkedIn, portfolio |
| 2 | Career Interests | Target roles and industry |
| 3 | Skills | Technical and soft skills |
| 4 | Education | Institution, degree, GPA |
| 5 | Experience | Company, role, dates, description |
| 6 | Projects | Title, description, technologies, URL |
| 7 | Certifications | Name, issuer, date |
| 8 | Achievements | Awards, publications |
| 9 | Review & Confirm | Summary shown, edits accepted |
| 10 | Template Selection | AI recommends from 5 templates |
| 11 | Preview & Refine | HTML preview, conversational edits |
| 12 | Export | PDF or DOCX download |

**Post-build pipeline**: finalize → Resume Analyzer (extract skills + score) → Orchestrator trigger → Scout + Analyst → user lands on recommendations automatically.

**5 ATS-friendly templates** stored in `backend/templates/`:
- `minimal_ats.html` — All roles
- `developer_modern.html` — Software / Tech
- `corporate_classic.html` — Business / Management
- `student_simple.html` — Freshers
- `technical_professional.html` — Senior / Research

### Interview Agent — Full Spec: `interview_prep_agent.md`

**Session lifecycle:** Setup → Mock Interview (10 Q's) → Evaluation → Feedback Report

**Question breakdown per session:**
- 3 Technical (role-specific)
- 2 Technical (project-based, from user's own resume)
- 3 Behavioral (STAR format)
- 2 Situational (from job description context)

**Answer evaluated on**: correctness, depth, clarity, relevance (technical); STAR structure, specificity, impact (behavioral)

**Readiness levels**: Ready (≥75) · Almost Ready (55–74) · Needs Prep (<55)

### LinkedIn Agent — Full Spec: `linkedin_optimizer_agent.md`

**What it analyzes**: Gap between user's resume data (in DB) and LinkedIn sections they paste in.

**Output sections**:
- 3 headline variants (keyword-rich, achievement-led, role-focused)
- Full about section draft
- Before/after for every experience bullet
- Skills to add / remove / reorder
- Profile completeness score (0–100)

**Important**: Does not scrape LinkedIn. User pastes their profile sections as text. Fully ToS-compliant.

---

## 4. Database Schema

### Complete Table Inventory — 25 Tables

**Core Tables (Original)**

| Table | Purpose |
|---|---|
| `users` | User accounts |
| `resumes` | Resume file metadata |
| `resume_data` | Parsed resume contact info |
| `education` | Education entries per resume |
| `experience` | Work experience entries |
| `projects` | Project entries |
| `skills` | Extracted skills per resume |
| `internships` | Scraped job listings |
| `internship_skills` | Required skills per listing |
| `recommendations` | User-internship match scores |
| `applications` | User application tracking |
| `notifications` | In-app notifications |
| `chat_logs` | Bolt AI conversation history |
| `password_reset_tokens` | Password reset flow |

**Agent Tables**

| Table | Agent | Purpose |
|---|---|---|
| `agent_state` | Orchestrator | Current shared state per user |
| `agent_runs` | Orchestrator | Full audit log of every agent execution |
| `skill_snapshots` | Analyst | Weekly skill demand snapshots for trend analysis |
| `cover_letter_drafts` | Writer | Drafts pending user review |
| `builder_sessions` | Builder | Resume creation session state |
| `resume_versions` | Builder | Full version history of built resumes |
| `interview_sessions` | Interview | Session state and scores |
| `interview_questions` | Interview | Generated questions per session |
| `interview_answers` | Interview | User answers + evaluations |
| `interview_reports` | Interview | Final feedback reports |
| `linkedin_sessions` | LinkedIn | Analysis session state |
| `linkedin_reports` | LinkedIn | Optimization reports |

### Key Table Definitions

```sql
-- Core user table
CREATE TABLE users (
    id                          SERIAL PRIMARY KEY,
    email                       VARCHAR(255) UNIQUE NOT NULL,
    password_hash               VARCHAR(255) NOT NULL,
    name                        VARCHAR(255) NOT NULL,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    email_notifications_enabled BOOLEAN DEFAULT TRUE
);
CREATE INDEX idx_users_email ON users(email);

-- Resume file metadata (1 per user)
CREATE TABLE resumes (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_name   VARCHAR(255) NOT NULL,
    file_path   VARCHAR(500) NOT NULL,
    file_type   VARCHAR(10) NOT NULL,
    file_size   INTEGER NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analyzed    BOOLEAN DEFAULT FALSE,
    score       INTEGER,
    feedback    TEXT[],
    UNIQUE(user_id)
);

-- Internship listings
CREATE TABLE internships (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(255) NOT NULL,
    company         VARCHAR(255) NOT NULL,
    location        VARCHAR(255) NOT NULL,
    description     TEXT NOT NULL,
    application_url VARCHAR(500) NOT NULL,
    source          VARCHAR(50) NOT NULL,
    posted_date     DATE,
    salary_range    VARCHAR(100),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duplicate_hash  VARCHAR(64) UNIQUE  -- SHA256 of title|company|location
);

-- Agent orchestration state
CREATE TABLE agent_state (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    state_json  JSONB NOT NULL DEFAULT '{}',
    last_run_at TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent run audit log
CREATE TABLE agent_runs (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_name    VARCHAR(50) NOT NULL,  -- 'scout'|'analyst'|'coach'|'writer'|'builder'|'interview'|'linkedin'|'orchestrator'
    trigger       VARCHAR(100) NOT NULL,
    input_json    JSONB,
    output_json   JSONB,
    status        VARCHAR(20) NOT NULL,  -- 'running'|'success'|'failed'
    error_message TEXT,
    started_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at  TIMESTAMP
);

-- Weekly skill trend snapshots
CREATE TABLE skill_snapshots (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_date   DATE NOT NULL,
    skill_name      VARCHAR(100) NOT NULL,
    frequency_pct   FLOAT NOT NULL,
    trend           VARCHAR(20),  -- 'rising'|'stable'|'falling'
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resume builder sessions
CREATE TABLE builder_sessions (
    id                SERIAL PRIMARY KEY,
    session_id        VARCHAR(100) UNIQUE NOT NULL,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_step      INTEGER NOT NULL DEFAULT 1,
    resume_data       JSONB NOT NULL DEFAULT '{}',
    selected_template VARCHAR(100),
    status            VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resume version history
CREATE TABLE resume_versions (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    resume_data    JSONB NOT NULL,
    template_name  VARCHAR(100),
    ats_score      INTEGER,
    source         VARCHAR(20) NOT NULL DEFAULT 'builder',  -- 'builder'|'upload'|'edit'
    pdf_path       VARCHAR(500),
    docx_path      VARCHAR(500),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, version_number)
);

-- Interview sessions
CREATE TABLE interview_sessions (
    id              SERIAL PRIMARY KEY,
    session_id      VARCHAR(100) UNIQUE NOT NULL,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    internship_id   INTEGER NOT NULL REFERENCES internships(id) ON DELETE CASCADE,
    status          VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    overall_score   FLOAT,
    readiness_level VARCHAR(20),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP
);

-- Interview questions
CREATE TABLE interview_questions (
    id            SERIAL PRIMARY KEY,
    session_id    VARCHAR(100) NOT NULL REFERENCES interview_sessions(session_id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    category      VARCHAR(20) NOT NULL,  -- 'technical'|'behavioral'|'situational'
    difficulty    VARCHAR(10),
    skill_tested  VARCHAR(100),
    order_index   INTEGER NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Interview answers + evaluations
CREATE TABLE interview_answers (
    id              SERIAL PRIMARY KEY,
    question_id     INTEGER NOT NULL REFERENCES interview_questions(id) ON DELETE CASCADE,
    session_id      VARCHAR(100) NOT NULL,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    answer_text     TEXT NOT NULL,
    score           FLOAT,
    verdict         VARCHAR(20),
    strengths       TEXT[],
    weaknesses      TEXT[],
    model_answer    TEXT,
    improvement_tip TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Interview feedback reports
CREATE TABLE interview_reports (
    id                   SERIAL PRIMARY KEY,
    session_id           VARCHAR(100) UNIQUE NOT NULL,
    user_id              INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    internship_id        INTEGER NOT NULL REFERENCES internships(id),
    overall_score        FLOAT NOT NULL,
    technical_score      FLOAT NOT NULL,
    behavioral_score     FLOAT NOT NULL,
    readiness_level      VARCHAR(20) NOT NULL,
    top_strengths        TEXT[] NOT NULL,
    top_improvements     TEXT[] NOT NULL,
    recommended_resources TEXT[],
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LinkedIn optimization sessions
CREATE TABLE linkedin_sessions (
    id            SERIAL PRIMARY KEY,
    session_id    VARCHAR(100) UNIQUE NOT NULL,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_input JSONB NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LinkedIn optimization reports
CREATE TABLE linkedin_reports (
    id                      SERIAL PRIMARY KEY,
    session_id              VARCHAR(100) UNIQUE NOT NULL REFERENCES linkedin_sessions(session_id),
    user_id                 INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_score           INTEGER NOT NULL,
    score_breakdown         JSONB NOT NULL,
    gap_analysis            JSONB NOT NULL,
    headline_variants       JSONB NOT NULL,
    about_section           TEXT,
    experience_improvements JSONB,
    skills_optimization     JSONB,
    improvement_priority    TEXT[] NOT NULL,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Migration Strategy

- Alembic manages all schema changes with versioned, reversible migrations
- FK constraints enforce referential integrity throughout
- All indexes defined at migration time
- Cascade deletes ensure no orphaned records on user deletion

---

## 5. Backend Design

### Project Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI entry point, CORS, middleware
│   ├── database.py                # Engine, SessionLocal, Base, DB dependency
│   ├── models/                    # SQLAlchemy ORM models (1 file per table group)
│   ├── routes/                    # FastAPI route handlers
│   ├── services/                  # Business logic layer
│   ├── utils/                     # Shared utilities (logging, hashing, etc.)
│   │
│   ├── orchestrator/              # Orchestrator Agent
│   ├── scout_agent/               # Scout Agent
│   ├── analyst_agent/             # Analyst Agent
│   ├── coach_agent/               # Coach Agent
│   ├── writer_agent/              # Writer Agent
│   ├── resume_agent/              # Builder Agent
│   │   ├── resume_routes.py
│   │   ├── resume_service.py
│   │   ├── resume_schema.py
│   │   ├── template_engine.py
│   │   ├── resume_optimizer.py
│   │   └── export_service.py
│   ├── interview_agent/           # Interview Agent
│   │   ├── interview_routes.py
│   │   ├── interview_service.py
│   │   ├── interview_schema.py
│   │   ├── question_generator.py
│   │   ├── answer_evaluator.py
│   │   └── feedback_reporter.py
│   └── linkedin_agent/            # LinkedIn Agent
│       ├── linkedin_routes.py
│       ├── linkedin_service.py
│       ├── linkedin_schema.py
│       ├── gap_analyzer.py
│       ├── content_optimizer.py
│       └── profile_scorer.py
│
├── templates/                     # Jinja2 resume templates
│   ├── minimal_ats.html
│   ├── developer_modern.html
│   ├── corporate_classic.html
│   ├── student_simple.html
│   └── technical_professional.html
│
├── migrations/                    # Alembic migration files
├── tests/                         # All test files
├── requirements.txt
└── render.yaml
```

### Core Services

**AuthService** — JWT + bcrypt
```python
class AuthService:
    def register_user(email, password, name) -> User
    def login_user(email, password) -> dict           # Returns JWT
    def verify_token(token) -> User
    def hash_password(password) -> str                # bcrypt, rounds=12
    def generate_reset_token(email) -> str            # 1h expiration
    def validate_reset_token(token) -> User
```

**ResumeAnalyzer** — spaCy NLP pipeline
```python
class ResumeAnalyzer:
    def extract_text(file_path, file_type) -> str     # PyPDF2 / python-docx
    def parse_contact_info(text) -> ContactInfo       # NER + Regex
    def parse_education(text) -> list[Education]
    def parse_experience(text) -> list[Experience]
    def extract_skills(text) -> list[Skill]           # NER + keyword matching
    def calculate_score(resume_data) -> tuple[int, list[str]]
```

**Scoring algorithm**: Sections (40) + Skill Diversity (30) + Experience (15) + Education (10) + Projects (5) = **100**

**RecommendationEngine** — TF-IDF cosine similarity
```python
class RecommendationEngine:
    def get_recommendations(user_id, limit=20) -> list[InternshipRecommendation]
    # TF-IDF config: max_features=500, ngram_range=(1,2), threshold≥0.3
    # Match quality: ≥0.7 Excellent | 0.5-0.7 Good | 0.3-0.5 Fair
```

**CareerPathPredictor** — Rule-based
```python
class CareerPathPredictor:
    def generate_paths(profile) -> list[CareerPath]  # Returns 3-5 paths
    # Entry (0-1yr), Mid (2-3yr), Senior (5+yr) — ranked by alignment score
```

### Middleware & Cross-Cutting Concerns

| Concern | Detail |
|---|---|
| Rate limiting | 10/min unauth, 100/min auth, 20/min Bolt, 5/min file upload — HTTP 429 |
| Error handling | Global handler; structured JSON errors; stack trace logged, not exposed |
| CORS | Frontend domain only |
| Logging | Structured JSON, rotation, 7-day free / 30-day paid retention |
| Background tasks | FastAPI `BackgroundTasks` or Celery for non-blocking agent execution |

### Error Response Format
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": {}
  }
}
```

---

## 6. AI & ML Modules

### Resume Analyzer (spaCy)

```
PDF/DOCX → Text Extraction (PyPDF2 / python-docx) → spaCy (en_core_web_sm)
  → Parallel Extraction:
    ├─ Contact Info (NER + Regex)
    ├─ Education (Pattern Matching)
    ├─ Experience (Pattern Matching)
    ├─ Projects (Section Detection)
    └─ Skills (NER + Keyword Matching)
  → Normalize → Score → Store in DB
```

### Recommendation Engine (scikit-learn)

```
User Skills ──────────────────┐
                              ├── TF-IDF → Cosine Similarity → Filter ≥0.3 → Top 20
Internship Requirements ──────┘
```

### Career Path Predictor (Rule-based)

Returns 3–5 paths ranked by alignment score. Entry/Mid/Senior levels derived from skill overlap and experience.

### Bolt AI Assistant (OpenAI GPT-4)

**5 Intent modes**: Navigation · Resume Coach · Job Search · Career Mentor · Skill Advisor

Modes auto-detected by keyword classification. Each mode builds a different system prompt with relevant DB context (user profile, resume, recommendations, career paths, chat history). Streaming enabled.

**Coach Agent integration**: Bolt reads the latest `coaching_brief` from the Coach Agent as additional context — making it proactive rather than reactive.

### Builder Agent — Resume Optimizer (LLM)

```
"made a website"
  → "Developed a responsive web application using React and Node.js,
     improving user engagement by 40%"
```

ATS score: Structure (35) + Keyword Density (40) + Completeness (25) = **100**

### Interview Agent — Question Generator + Answer Evaluator (LLM)

Question generation: role category detection → 10 targeted questions (5 technical, 5 behavioral/situational) generated from job listing + user resume.

Answer evaluation: LLM scores each answer 0–10 on correctness, depth, clarity, relevance. Generates model answer and one improvement tip per question.

### LinkedIn Agent — Gap Analyzer + Content Optimizer (LLM)

Gap analysis: resume data (DB) vs. LinkedIn sections (user-pasted text). Generates 3 headline variants, full about section, per-bullet before/after improvements, skill reordering.

---

## 7. API Reference

### Complete Endpoint Inventory

All endpoints prefixed with `/api`. Protected endpoints require `Authorization: Bearer <token>`.

#### Authentication
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/auth/me` | Get current user profile |
| POST | `/api/auth/request-reset` | Send password reset email |
| POST | `/api/auth/reset-password` | Reset password with token |

#### Resume
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/resumes/upload` | Upload PDF/DOCX (max 10MB) |
| GET | `/api/resumes/me` | Get resume with score and skills |
| GET | `/api/resumes/analysis` | Detailed resume analysis |
| DELETE | `/api/resumes/me` | Delete resume |

#### Internships
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/internships` | Paginated list with search/filter |
| GET | `/api/internships/:id` | Single listing details |
| GET | `/api/internships/:id/skill-gap` | Skill gap for current user vs. listing |

#### Recommendations
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/recommendations` | Top 20 AI-matched listings |
| POST | `/api/recommendations/refresh` | Regenerate recommendations |

#### Career Tools
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/career/paths` | Career path predictions |
| POST | `/api/career/compare` | Compare 2–4 roles side-by-side |

#### Applications
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/applications` | Track new application |
| GET | `/api/applications` | List all applications (filter by status) |
| PATCH | `/api/applications/:id` | Update status or notes |
| DELETE | `/api/applications/:id` | Remove application |

#### Notifications
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/notifications` | List notifications |
| PATCH | `/api/notifications/:id/read` | Mark one as read |
| PATCH | `/api/notifications/read-all` | Mark all as read |

#### Bolt AI
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/bolt/chat` | Send message, get response |
| GET | `/api/bolt/history` | Chat history for session |
| DELETE | `/api/bolt/history/:session_id` | Delete session history |

#### Agent Control
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/agent/trigger` | Manually trigger Orchestrator |
| GET | `/api/agent/status` | Current agent state + last run |
| GET | `/api/agent/runs` | Agent run history |
| GET | `/api/agent/runs/:id` | Single run detail |

#### Skill Snapshots (Analyst Agent)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/skills/snapshots` | All snapshots for trend chart |
| GET | `/api/skills/trends` | Latest trend report |

#### Cover Letter Drafts (Writer Agent)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/drafts` | All drafts |
| POST | `/api/drafts/generate` | Trigger Writer Agent for listing |
| PATCH | `/api/drafts/:id` | Edit draft |
| PATCH | `/api/drafts/:id/approve` | Approve draft |
| DELETE | `/api/drafts/:id` | Discard draft |

#### Coach Agent
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/coach/brief` | Latest coaching brief |
| GET | `/api/coach/history` | Past coaching briefs |

#### Resume Builder Agent
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/resume-agent/start-session` | Start builder, get first question |
| POST | `/api/resume-agent/answer` | Submit answer, get next question |
| GET | `/api/resume-agent/session/:id` | Session state and progress |
| GET | `/api/resume-agent/templates` | Available templates |
| POST | `/api/resume-agent/select-template` | Choose template |
| GET | `/api/resume-agent/preview/:id` | Rendered HTML preview |
| POST | `/api/resume-agent/update-section` | Update a resume section |
| POST | `/api/resume-agent/optimize` | Run LLM optimization |
| GET | `/api/resume-agent/ats-score/:id` | ATS score breakdown |
| POST | `/api/resume-agent/finalize` | Finalize + trigger pipeline |
| POST | `/api/resume-agent/export-pdf` | Generate PDF download |
| POST | `/api/resume-agent/export-docx` | Generate DOCX download |
| GET | `/api/resume-agent/versions` | Version history |
| GET | `/api/resume-agent/versions/:id` | Specific version |
| POST | `/api/resume-agent/versions/:id/restore` | Restore version |

#### Interview Agent
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/interview/start` | Start session, get first question |
| GET | `/api/interview/session/:id` | Session state |
| POST | `/api/interview/answer` | Submit answer, get next question |
| POST | `/api/interview/complete` | Evaluate + generate report |
| GET | `/api/interview/report/:id` | Full feedback report |
| GET | `/api/interview/history` | Past sessions |
| POST | `/api/interview/retry/:id` | Restart with new questions |
| GET | `/api/interview/questions/:id` | All questions (review mode) |

#### LinkedIn Agent
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/linkedin/analyze` | Submit profile, trigger analysis |
| GET | `/api/linkedin/report/:id` | Full optimization report |
| POST | `/api/linkedin/regenerate` | Regenerate a section with feedback |
| GET | `/api/linkedin/score/:id` | Profile score breakdown |
| GET | `/api/linkedin/history` | Past sessions |
| GET | `/api/linkedin/latest` | Most recent report |

#### User Settings & Health
| Method | Endpoint | Description |
|---|---|---|
| PATCH | `/api/users/settings` | Update email notification toggle |
| DELETE | `/api/users/me` | Delete account + all data |
| GET | `/health` | Health check |

### Rate Limits Summary

| Type | Limit |
|---|---|
| Unauthenticated | 10 req/min per IP |
| Authenticated (general) | 100 req/min per user |
| Bolt chat | 20 req/min per user |
| File upload | 5 req/min per user |
| Resume builder | 10 req/min per user |
| Interview answer | 30 req/min per user |
| LinkedIn analyze | 5 req/min per user |

---

## 8. Frontend Design

### Technology Stack

| Tool | Purpose |
|---|---|
| React + TypeScript | Component framework |
| Tailwind CSS | Utility-first styling |
| React Router | Client-side routing |
| Axios | HTTP client |
| Vite | Build tool (Node 18.x) |

### Page Inventory

| Page | Route | Description |
|---|---|---|
| Register | `/register` | Sign up form |
| Login | `/login` | Login form |
| Password Reset | `/reset` | Request / confirm reset |
| Dashboard | `/` | Score summary, quick links, notification badge |
| Resume | `/resume` | Upload OR "Create with AI" — splits to Builder |
| Builder | `/resume/build` | 12-step conversation UI |
| Listings | `/internships` | Paginated + filterable listing cards |
| Listing Detail | `/internships/:id` | Full detail + skill gap + apply button |
| Recommendations | `/recommendations` | Top 20 AI-matched with match cards |
| Career Tools | `/career` | Path Predictor + Role Comparator |
| Applications | `/applications` | Tracker with status + notes |
| Cover Letters | `/drafts` | Writer Agent output — review and approve |
| Interview Prep | `/interview` | Start session / view history |
| Interview Session | `/interview/:id` | Live Q&A chat UI |
| Interview Report | `/interview/:id/report` | Feedback report with scores |
| LinkedIn Optimizer | `/linkedin` | Paste profile / view report |
| Skills Dashboard | `/skills` | Analyst trend chart + snapshots |
| Notifications | `/notifications` | Full notification center |
| Settings | `/settings` | Notification toggle + delete account |

### Bolt AI Chat Widget

- Floating bottom-right; expand/collapse preserves session history
- Typing indicator while generating
- Reads latest Coach Agent brief as context
- 5 auto-detected modes: Navigation · Resume Coach · Job Search · Career Mentor · Skill Advisor

### Responsive Breakpoints

| Breakpoint | Min Width |
|---|---|
| Mobile | 320px |
| Tablet | 768px |
| Desktop | 1024px |

### Security (Frontend)

- JWT in memory only — not localStorage
- CSP headers via Vercel config
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`

---

## 9. Notification System

### Notification Types

| Type | Trigger |
|---|---|
| `NEW_RECOMMENDATIONS` | Post-Scout new matches found |
| `APPLICATION_UPDATE` | Status changed on tracked application |
| `RESUME_ANALYZED` | Analysis complete (upload or Builder) |
| `INTERVIEW_REPORT_READY` | Interview evaluation complete |
| `LINKEDIN_REPORT_READY` | LinkedIn analysis complete |
| `COACHING_BRIEF` | Coach Agent generated new brief |
| `SYSTEM_UPDATE` | Platform announcements |

### Email Strategy

- Daily digest: max 1 email/user/day
- Top 5 new matching internships with title, company, link
- Only sent if `email_notifications_enabled = TRUE`
- Failed delivery: retry once after 1 hour

### In-App Strategy

- Stored in `notifications` table, reverse chronological
- Badge count on notification icon
- Auto-deleted after 30 days

---

## 10. Testing Strategy

### Frameworks

| Layer | Tools |
|---|---|
| Backend | pytest, pytest-asyncio, Hypothesis (property-based), faker, pytest-cov |
| Frontend | Jest, React Testing Library, fast-check (100 runs), MSW |

### Coverage Goals

| Scope | Target |
|---|---|
| Backend overall | ≥ 80% |
| Frontend overall | ≥ 70% |
| Critical paths | ≥ 90% |
| Property tests (dev) | 20 iterations |
| Property tests (CI) | 200 iterations |

### Test Structure

```
tests/
├── unit/               # Specific example tests
├── property/           # Hypothesis property tests
├── integration/        # API + DB integration tests
└── conftest.py         # Shared fixtures
```

### Key Property Tests (66 total + agent additions)

Categories covered: Authentication (4) · Resume (8) · Scraper (5) · Recommendation (4) · Skill/Career (8) · Applications (4) · Notifications (9) · Bolt AI (15) · API Security (3) · Database (2) · Error Handling (4) · Builder Agent (4) · Interview Agent (4) · LinkedIn Agent (3)

---

## 11. Deployment

### Infrastructure

| Component | Service | Notes |
|---|---|---|
| Frontend | Vercel | Auto-deploy from `main`; preview per PR |
| Backend | Render / Railway | Python 3.11; auto-scaling; health checks |
| Database | Supabase / Neon | PostgreSQL 15+; daily backups; 7-day PITR |
| File Storage | Cloudflare R2 | S3-compatible; no egress fees |

### Backend Config (`render.yaml`)

```yaml
services:
  - type: web
    name: ai-career-backend
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn main:app --host 0.0.0.0 --port $PORT"
    healthCheckPath: /health

  - type: cron
    name: orchestrator-cron
    schedule: "0 */6 * * *"
    startCommand: "python -m app.orchestrator.run"
```

### Environment Variables

```
DATABASE_URL          JWT_SECRET            JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24                    OPENAI_API_KEY
SMTP_HOST             SMTP_PORT=587         SMTP_USERNAME
SMTP_PASSWORD         FRONTEND_URL          RATE_LIMIT_ENABLED=true
LOG_LEVEL=INFO        R2_ACCESS_KEY         R2_SECRET_KEY
```

### CI/CD Pipeline (GitHub Actions)

```
PR opened → test-backend (pytest --cov) + test-frontend (npm test + build)
Merge to main → auto-deploy backend (Render hook) + frontend (Vercel)
Post-deploy → alembic upgrade head → verify /health
```

### Cost Estimates

| Tier | Monthly Cost |
|---|---|
| MVP (free) | $0 — Vercel Hobby + Render free + Supabase free |
| Production | $105–205 — Vercel Pro + Render Starter + Supabase Pro + OpenAI |
| Scale | $430–900 — Pro tiers + Redis + higher AI usage |

---

## 12. Build Phases

| Phase | What Gets Built |
|---|---|
| **0 — Foundation** | FastAPI scaffolding, PostgreSQL setup, Alembic migrations, auth system, project structure |
| **1 — Resume Upload** | File upload, S3/R2 integration, resume storage |
| **2 — Resume Analysis** | spaCy NLP pipeline, skill extraction, scoring |
| **3 — Scout Agent** | Scraper + agent reasoning layer, per-user listing scoring, `agent_runs` |
| **4 — Recommendation Engine** | TF-IDF vectorization, cosine similarity, recommendations table |
| **5 — Analyst Agent** | Skill snapshots, trend detection, skill dashboard |
| **6 — Orchestrator** | Agent state, Scout→Analyst pipeline, autonomous loop |
| **7 — Writer Agent** | Cover letter drafting, draft review UI |
| **8 — Coach Agent** | Coaching briefs, proactive notifications, Bolt context |
| **9 — Builder Agent** | 12-step conversation, Jinja2 templates, PDF/DOCX export, post-build pipeline |
| **10 — Interview Agent** | Question generation, answer evaluation, feedback reports |
| **11 — LinkedIn Agent** | Gap analysis, content optimization, profile score |
| **12 — Frontend** | All React pages, Bolt widget, responsive design |
| **13 — Notifications** | Email digest, in-app alerts, all notification types |
| **14 — Testing** | Property tests, integration tests, coverage targets |
| **15 — Deployment** | CI/CD, Vercel + Render config, monitoring |
| **16 — Polish** | Agent run history UI, demo preparation, performance tuning |

---

## 13. Document Index

| File | Contents |
|---|---|
| `00_FINAL_DOCUMENTATION.md` | **This file** — complete combined reference |
| `01_BACKEND.md` | Backend phase-by-phase implementation guide |
| `02_DATABASE.md` | Database phase-by-phase setup and migrations |
| `03_AGENTS.md` | All 7 agents + Orchestrator, phase-by-phase |
| `04_FRONTEND.md` | Frontend phase-by-phase implementation guide |
| `05_TESTING.md` | Testing strategy and all property tests |
| `06_DEPLOYMENT.md` | Deployment and CI/CD phase-by-phase |

---

*Document complete. All 7 agents defined. 25 tables specified. 70+ API endpoints documented. 16 build phases sequenced. Ready to build.*
