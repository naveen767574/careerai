# Database Implementation Guide
## AI-Powered Internship & Career Recommendation System

> Phase-by-phase database setup, schema, and migrations.
> Stack: PostgreSQL 15+ · SQLAlchemy ORM · Alembic Migrations

---

## Overview

- **25 total tables** across 8 migration phases
- **Alembic** manages all schema changes (versioned, reversible)
- **SSL required** for all connections; PgBouncer connection pooling
- **Cascade deletes** on all user-owned tables

---

## Phase 0 — Connection & Initial Setup

```python
# app/database.py
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

```bash
alembic init migrations
alembic revision --autogenerate -m "initial_tables"
alembic upgrade head
```

### Migration 001 — Users

```sql
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

CREATE TABLE password_reset_tokens (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used       BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_reset_tokens_token   ON password_reset_tokens(token);
CREATE INDEX idx_reset_tokens_expires ON password_reset_tokens(expires_at);
```

---

## Phase 1 — Resume Tables

### Migration 002

```sql
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
CREATE INDEX idx_resumes_user_id ON resumes(user_id);

CREATE TABLE resume_data (
    id            SERIAL PRIMARY KEY,
    resume_id     INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    contact_name  VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    raw_text      TEXT,
    UNIQUE(resume_id)
);

CREATE TABLE education (
    id              SERIAL PRIMARY KEY,
    resume_id       INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    institution     VARCHAR(255) NOT NULL,
    degree          VARCHAR(255) NOT NULL,
    field_of_study  VARCHAR(255),
    graduation_date DATE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_education_resume_id ON education(resume_id);

CREATE TABLE experience (
    id          SERIAL PRIMARY KEY,
    resume_id   INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    company     VARCHAR(255) NOT NULL,
    role        VARCHAR(255) NOT NULL,
    start_date  DATE,
    end_date    DATE,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_experience_resume_id ON experience(resume_id);

CREATE TABLE projects (
    id           SERIAL PRIMARY KEY,
    resume_id    INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    title        VARCHAR(255) NOT NULL,
    description  TEXT,
    technologies TEXT[],
    url          VARCHAR(500),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_projects_resume_id ON projects(resume_id);

CREATE TABLE skills (
    id         SERIAL PRIMARY KEY,
    resume_id  INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    skill_name VARCHAR(100) NOT NULL,
    skill_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_skills_resume_id ON skills(resume_id);
CREATE INDEX idx_skills_name      ON skills(skill_name);
```

---

## Phase 2 — Internship & Recommendation Tables

### Migration 003

```sql
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
    duplicate_hash  VARCHAR(64) UNIQUE
);
CREATE INDEX idx_internships_company  ON internships(company);
CREATE INDEX idx_internships_location ON internships(location);
CREATE INDEX idx_internships_active   ON internships(is_active);
CREATE INDEX idx_internships_source   ON internships(source);

CREATE TABLE internship_skills (
    id             SERIAL PRIMARY KEY,
    internship_id  INTEGER NOT NULL REFERENCES internships(id) ON DELETE CASCADE,
    skill_name     VARCHAR(100) NOT NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_internship_skills_internship_id ON internship_skills(internship_id);
CREATE INDEX idx_internship_skills_name          ON internship_skills(skill_name);

CREATE TABLE recommendations (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    internship_id    INTEGER NOT NULL REFERENCES internships(id) ON DELETE CASCADE,
    similarity_score FLOAT NOT NULL,
    match_percentage FLOAT NOT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, internship_id)
);
CREATE INDEX idx_recommendations_user_id ON recommendations(user_id);
CREATE INDEX idx_recommendations_score   ON recommendations(similarity_score DESC);
```

---

## Phase 3 — Application & Communication Tables

### Migration 004

```sql
CREATE TABLE applications (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    internship_id INTEGER NOT NULL REFERENCES internships(id) ON DELETE CASCADE,
    status        VARCHAR(50) NOT NULL DEFAULT 'APPLIED',
    applied_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, internship_id)
);
CREATE INDEX idx_applications_user_id ON applications(user_id);
CREATE INDEX idx_applications_status  ON applications(status);

CREATE TABLE notifications (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type       VARCHAR(50) NOT NULL,
    title      VARCHAR(255) NOT NULL,
    content    TEXT NOT NULL,
    is_read    BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_read    ON notifications(is_read);
CREATE INDEX idx_notifications_created ON notifications(created_at DESC);

CREATE TABLE chat_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id      VARCHAR(100) NOT NULL,
    message_type    VARCHAR(20) NOT NULL,
    message_content TEXT NOT NULL,
    intent          VARCHAR(50),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_chat_logs_user_id    ON chat_logs(user_id);
CREATE INDEX idx_chat_logs_session_id ON chat_logs(session_id);
CREATE INDEX idx_chat_logs_created    ON chat_logs(created_at DESC);
```

---

## Phase 4 — Agent Infrastructure Tables

### Migration 005

```sql
CREATE TABLE agent_state (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    state_json  JSONB NOT NULL DEFAULT '{}',
    last_run_at TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agent_runs (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_name    VARCHAR(50) NOT NULL,
    trigger       VARCHAR(100) NOT NULL,
    input_json    JSONB,
    output_json   JSONB,
    status        VARCHAR(20) NOT NULL,
    error_message TEXT,
    started_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at  TIMESTAMP
);
CREATE INDEX idx_agent_runs_user_id    ON agent_runs(user_id);
CREATE INDEX idx_agent_runs_agent_name ON agent_runs(agent_name);
CREATE INDEX idx_agent_runs_status     ON agent_runs(status);

CREATE TABLE skill_snapshots (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    skill_name    VARCHAR(100) NOT NULL,
    frequency_pct FLOAT NOT NULL,
    trend         VARCHAR(20),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_skill_snapshots_user_id ON skill_snapshots(user_id);
CREATE INDEX idx_skill_snapshots_date    ON skill_snapshots(snapshot_date DESC);

CREATE TABLE cover_letter_drafts (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    internship_id INTEGER NOT NULL REFERENCES internships(id) ON DELETE CASCADE,
    content       TEXT NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'draft',
    agent_run_id  INTEGER REFERENCES agent_runs(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_cover_letter_drafts_user_id ON cover_letter_drafts(user_id);
CREATE INDEX idx_cover_letter_drafts_status  ON cover_letter_drafts(status);
```

---

## Phase 5 — Builder Agent Tables

### Migration 006

```sql
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
CREATE INDEX idx_builder_sessions_user_id ON builder_sessions(user_id);

CREATE TABLE resume_versions (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    resume_data    JSONB NOT NULL,
    template_name  VARCHAR(100),
    ats_score      INTEGER,
    source         VARCHAR(20) NOT NULL DEFAULT 'builder',
    pdf_path       VARCHAR(500),
    docx_path      VARCHAR(500),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, version_number)
);
CREATE INDEX idx_resume_versions_user_id ON resume_versions(user_id);
```

---

## Phase 6 — Interview Agent Tables

### Migration 007

```sql
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
CREATE INDEX idx_interview_sessions_user_id ON interview_sessions(user_id);

CREATE TABLE interview_questions (
    id            SERIAL PRIMARY KEY,
    session_id    VARCHAR(100) NOT NULL REFERENCES interview_sessions(session_id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    category      VARCHAR(20) NOT NULL,
    difficulty    VARCHAR(10),
    skill_tested  VARCHAR(100),
    order_index   INTEGER NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_interview_questions_session ON interview_questions(session_id);

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
CREATE INDEX idx_interview_answers_session  ON interview_answers(session_id);
CREATE INDEX idx_interview_answers_user_id  ON interview_answers(user_id);

CREATE TABLE interview_reports (
    id                    SERIAL PRIMARY KEY,
    session_id            VARCHAR(100) UNIQUE NOT NULL,
    user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    internship_id         INTEGER NOT NULL REFERENCES internships(id),
    overall_score         FLOAT NOT NULL,
    technical_score       FLOAT NOT NULL,
    behavioral_score      FLOAT NOT NULL,
    readiness_level       VARCHAR(20) NOT NULL,
    top_strengths         TEXT[] NOT NULL,
    top_improvements      TEXT[] NOT NULL,
    recommended_resources TEXT[],
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_interview_reports_user_id ON interview_reports(user_id);
```

---

## Phase 7 — LinkedIn Agent Tables

### Migration 008

```sql
CREATE TABLE linkedin_sessions (
    id            SERIAL PRIMARY KEY,
    session_id    VARCHAR(100) UNIQUE NOT NULL,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_input JSONB NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_linkedin_sessions_user_id ON linkedin_sessions(user_id);

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
CREATE INDEX idx_linkedin_reports_user_id ON linkedin_reports(user_id);
```

---

## Scheduled Maintenance

| Job | Schedule | SQL |
|---|---|---|
| Cleanup notifications | Daily 2am | `DELETE FROM notifications WHERE created_at < NOW() - INTERVAL '30 days'` |
| Cleanup reset tokens | Daily 2am | `DELETE FROM password_reset_tokens WHERE expires_at < NOW()` |
| Cleanup chat logs | Weekly | `DELETE FROM chat_logs WHERE created_at < NOW() - INTERVAL '90 days'` |
| Cleanup abandoned sessions | Weekly | `DELETE FROM builder_sessions WHERE status='abandoned' AND updated_at < NOW() - INTERVAL '7 days'` |

---

## Migration Commands

```bash
alembic revision --autogenerate -m "description"  # Create migration
alembic upgrade head                               # Apply all
alembic upgrade +1                                 # Apply one
alembic downgrade -1                               # Rollback one
alembic current                                    # Show current state
alembic history --verbose                          # Full history
```
