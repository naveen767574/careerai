# Backend Setup Guide
## AI-Powered Internship and Career Recommendation System

> Complete step-by-step instructions to set up, run, and verify the backend locally.
> Stack: FastAPI, PostgreSQL, SQLAlchemy, Alembic, Groq, Supabase Storage

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Structure](#2-project-structure)
3. [Installation](#3-installation)
4. [Environment Variables](#4-environment-variables)
5. [Database Setup](#5-database-setup)
6. [Running the Server](#6-running-the-server)
7. [Verify Everything Works](#7-verify-everything-works)
8. [Running the Scraper](#8-running-the-scraper)
9. [Running the Agent System](#9-running-the-agent-system)
10. [API Reference](#10-api-reference)
11. [Common Errors and Fixes](#11-common-errors-and-fixes)
12. [Migration Commands](#12-migration-commands)

---

## 1. Prerequisites

Make sure you have the following installed before starting:

| Tool | Version | Check |
|---|---|---|
| Python | 3.11+ | `python --version` |
| PostgreSQL | 15+ | `psql --version` |
| pip | Latest | `pip --version` |
| Git | Any | `git --version` |

External services you will need:
- Groq API key: https://console.groq.com
- Supabase Storage: https://supabase.com
- Mailtrap for local email testing: https://mailtrap.io

---

## 2. Project Structure

```
backend/
+-- app/
|   +-- main.py              # FastAPI app, routers registered here
|   +-- config.py            # Settings loaded from .env
|   +-- database.py          # SQLAlchemy engine, session, get_db
|   +-- models/              # ORM models, one file per table
|   +-- routes/              # FastAPI routers, one per feature
|   +-- services/            # Business logic (no FastAPI imports)
|   +-- schemas/             # Pydantic request and response models
|   +-- scraper/             # 4-source web scraper and cron runner
|   +-- orchestrator/        # ReAct orchestrator loop
|   +-- agents/              # Scout, Analyst, Coach, Writer agents
|   +-- utils/               # Shared helpers
+-- alembic/                 # Database migrations (001-009)
+-- templates/               # Jinja2 resume HTML templates
+-- tests/                   # Unit and property-based tests
+-- requirements.txt         # Python dependencies
+-- render.yaml              # Production deployment config
+-- .env.example             # Copy to .env and fill values
+-- BACKEND_README.md        # This file
```

---

## 3. Installation

### Step 1 - Clone the repository

```bash
git clone <your-repo-url>
cd ai-career-platform/backend
```

### Step 2 - Create a virtual environment

```bash
python -m venv venv

# Activate it
source venv/bin/activate        # macOS or Linux
venv\Scripts\activate           # Windows
```

You should see `(venv)` at the start of your terminal prompt.

### Step 3 - Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 4 - Download the spaCy NLP model

```bash
python -m spacy download en_core_web_sm
```

### Step 5 - PDF export note

PDF export uses ReportLab and requires no system-level libraries on Windows.

---

## 4. Environment Variables

### Step 1 - Copy the example file

```bash
cp .env.example .env
```

### Step 2 - Fill in your values

Open `.env` and set the following:

```env
# Database
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/ai_career_dev

# Auth
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=your-long-random-secret-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Groq
GROQ_API_KEY=gsk-...

# Email (Mailtrap for local dev)
SMTP_HOST=smtp.mailtrap.io
SMTP_PORT=587
SMTP_USERNAME=your_mailtrap_username
SMTP_PASSWORD=your_mailtrap_password

# CORS
FRONTEND_URL=http://localhost:5173

# Supabase Storage
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here
SUPABASE_BUCKET=resumes

# Dev settings
RATE_LIMIT_ENABLED=false
LOG_LEVEL=DEBUG
```

### Where to get each value

| Variable | How to get it |
|---|---|
| `DATABASE_URL` | Your local PostgreSQL connection string |
| `JWT_SECRET` | Run: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `GROQ_API_KEY` | https://console.groq.com -> API Keys |
| `SMTP_*` | Mailtrap inbox settings: https://mailtrap.io |
| `SUPABASE_URL` | Supabase Project Settings -> API -> Project URL |
| `SUPABASE_SERVICE_KEY` | Supabase Project Settings -> API -> service_role key |
| `SUPABASE_BUCKET` | Name of your storage bucket (default: resumes) |

---

## 5. Database Setup

### Step 1 - Create the PostgreSQL database

If using local PostgreSQL:

```bash
psql -U postgres
CREATE DATABASE ai_career_dev;
\q
```

If using Supabase (free cloud DB):
1. Go to https://supabase.com and create a project
2. Project Settings -> Database -> Connection string -> URI
3. Copy the URI and paste it into `DATABASE_URL` in `.env`

### Step 2 - Run all migrations

```bash
alembic upgrade head
```

Expected output:
```
INFO  [alembic] Running upgrade  -> 001, create auth tables
INFO  [alembic] Running upgrade 001 -> 002, create resume tables
INFO  [alembic] Running upgrade 002 -> 003, create internship tables
INFO  [alembic] Running upgrade 003 -> 004, create application table
INFO  [alembic] Running upgrade 004 -> 005, create notification and chat tables
INFO  [alembic] Running upgrade 005 -> 006, create agent system tables
INFO  [alembic] Running upgrade 006 -> 007, create builder tables
INFO  [alembic] Running upgrade 007 -> 008, create interview tables
INFO  [alembic] Running upgrade 008 -> 009, create linkedin tables
```

If you see errors here, check that `DATABASE_URL` is correct and PostgreSQL is running.

### Step 3 - Verify tables were created

```bash
psql -U postgres -d ai_career_dev -c "\dt"
```

You should see all tables listed.

---

## 6. Running the Server

```bash
uvicorn app.main:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

`--reload` restarts the server when you change any Python file.

---

## 7. Verify Everything Works

Open the interactive API docs in your browser:

```
http://localhost:8000/docs
```

Then test these endpoints in order using Swagger UI or Postman or curl:

### Check 1 - Health
```
GET http://localhost:8000/health
Expected: { "status": "healthy", "database": "connected", "version": "1.0.0" }
```

### Check 2 - Register a user
```
POST http://localhost:8000/api/auth/register
Body: { "name": "Test User", "email": "test@example.com", "password": "Test1234!" }
Expected 201: { "user_id": 1, "email": "test@example.com" }
```

### Check 3 - Login and get token
```
POST http://localhost:8000/api/auth/login
Body: { "email": "test@example.com", "password": "Test1234!" }
Expected 200: { "access_token": "eyJ...", "token_type": "bearer" }
```

Copy the access token. Use it as `Authorization: Bearer <token>` for all steps below.

### Check 4 - Upload a resume
```
POST http://localhost:8000/api/resumes/upload
Header: Authorization: Bearer <token>
Body: multipart/form-data, key=file, value=<your PDF or DOCX>
Expected 201: { "resume_id": 1, "status": "uploaded" }
```

### Check 5 - Check resume analysis
```
GET http://localhost:8000/api/resumes/me
Header: Authorization: Bearer <token>
Expected 200: { "resume": { "score": 72, "feedback": [...] }, "skills": [...] }
```

### Check 6 - Get career paths
```
GET http://localhost:8000/api/career/paths
Header: Authorization: Bearer <token>
Expected 200: { "career_paths": [...], "total": 5 }
```

### Check 7 - Get notifications (empty list is fine)
```
GET http://localhost:8000/api/notifications
Header: Authorization: Bearer <token>
Expected 200: { "notifications": [], "total": 0, "unread_count": 0 }
```

### Check 8 - Bolt AI chat
```
POST http://localhost:8000/api/bolt/chat
Header: Authorization: Bearer <token>
Body: { "message": "What career paths suit me?", "session_id": "test-session-001" }
Expected 200: { "response": "...", "intent": "career_mentor" }
```

This requires a valid `GROQ_API_KEY`. If you get a 503, check your key.

### Check 9 - Start interview session (need internships first - see step 8)
```
POST http://localhost:8000/api/interview/start
Header: Authorization: Bearer <token>
Body: { "internship_id": 1 }
Expected 201: { "session_id": "...", "first_question": {...}, "total_questions": 10 }
```

### Check 10 - LinkedIn analysis
```
POST http://localhost:8000/api/linkedin/analyze
Header: Authorization: Bearer <token>
Body: {
  "headline": "Computer Science Student",
  "skills": ["Python", "React"],
  "has_photo": false
}
Expected 201: { "profile_score": 35, "headline_variants": {...}, ... }
```

---

## 8. Running the Scraper

The scraper populates the internships table. Run it manually:

```bash
python -m app.scraper.run
```

Watch the logs - you should see listings from each source.

After it completes, check:
```
GET http://localhost:8000/api/internships?page=1&limit=5
Expected 200: { "internships": [...], "total": int }
```

Then get recommendations:
```
GET http://localhost:8000/api/recommendations
Header: Authorization: Bearer <token>
Expected 200: { "recommendations": [...] }
```

---

## 9. Running the Agent System

Trigger the full agent pipeline manually:

```
POST http://localhost:8000/api/agent/trigger
Header: Authorization: Bearer <token>
Body: { "trigger": "manual" }
Expected 200: { "message": "Orchestrator triggered successfully" }
```

Check status:
```
GET http://localhost:8000/api/agent/status
Header: Authorization: Bearer <token>
Expected 200: { "completed_agents": ["scout", "analyst", "coach"], "recent_runs": [...] }
```

The agent system runs in the background.

---

## 10. API Reference

All endpoints are prefixed with `/api`. All protected endpoints require `Authorization: Bearer <token>`.

| Domain | Endpoints | Auth |
|---|---|---|
| Auth | `/auth/register`, `/auth/login`, `/auth/me`, `/auth/request-reset`, `/auth/reset-password` | Public and Protected |
| Resume | `/resumes/upload`, `/resumes/me`, `/resume/:id/analysis` | Protected |
| Internships | `/internships`, `/internships/:id`, `/internships/:id/skill-gap` | Public |
| Recommendations | `/recommendations`, `/recommendations/refresh` | Protected |
| Career Tools | `/career/paths`, `/career/compare`, `/skills/snapshots`, `/skills/trends` | Protected |
| Applications | `/applications` (CRUD) | Protected |
| Notifications | `/notifications`, `/notifications/:id/read`, `/notifications/read-all` | Protected |
| Bolt AI | `/bolt/chat`, `/bolt/history`, `/bolt/history/:session_id` | Protected |
| Agent | `/agent/trigger`, `/agent/status`, `/agent/runs`, `/agent/runs/:id` | Protected |
| Cover Letters | `/drafts`, `/drafts/generate`, `/drafts/:id` | Protected |
| Resume Builder | `/resume-agent/start-session`, `/resume-agent/answer`, `/resume-agent/preview/:id`, `/resume-agent/export-pdf`, `/resume-agent/export-docx`, `/resume-agent/versions` | Protected |
| Interview | `/interview/start`, `/interview/answer`, `/interview/complete`, `/interview/report/:id`, `/interview/history` | Protected |
| LinkedIn | `/linkedin/analyze`, `/linkedin/report/:id`, `/linkedin/regenerate`, `/linkedin/score/:id`, `/linkedin/latest` | Protected |

Interactive docs: http://localhost:8000/docs

---

## 11. Common Errors and Fixes

### connection refused on startup
Cause: PostgreSQL is not running.
```bash
# macOS
brew services start postgresql

# Ubuntu
sudo service postgresql start
```

### relation "users" does not exist
Cause: Migrations have not been run.
```bash
alembic upgrade head
```

### ModuleNotFoundError: No module named "spacy"
Cause: Virtual environment not active or dependencies not installed.
```bash
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 503 Bolt AI is not configured
Cause: GROQ_API_KEY is missing or invalid in .env.
Set a real key at https://console.groq.com.

### Supabase storage upload failed
Cause: SUPABASE_URL, SUPABASE_SERVICE_KEY, or SUPABASE_BUCKET is incorrect.
Verify the values in Supabase Project Settings -> API and Storage.

### alembic.util.exc.CommandError: Can't locate revision
Cause: Migration files are out of order or missing.
```bash
alembic history --verbose
alembic current
alembic upgrade head
```

---

## 12. Migration Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Roll back the last migration
alembic downgrade -1

# Roll back all migrations
alembic downgrade base

# See all migrations and their status
alembic history --verbose

# See which migration is currently applied
alembic current

# Generate a new migration after changing a model
alembic revision --autogenerate -m "describe what changed"
alembic upgrade head
```

---

## Production Deployment

| Service | Provider | Notes |
|---|---|---|
| Backend API | Render or Railway | Use render.yaml config |
| Database | Supabase or Neon | Free tier available |
| File Storage | Supabase Storage | Create a bucket named resumes |
| Frontend | Vercel | Auto-deploy from main branch |

Set the same environment variables in your production platform's dashboard.
