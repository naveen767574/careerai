# Testing Strategy
## AI-Powered Internship & Career Recommendation System

> Dual approach: unit tests (specific examples) + property-based tests (universal invariants).
> Backend: pytest + Hypothesis | Frontend: Jest + fast-check

---

## Overview

| Layer | Framework | Coverage Target |
|---|---|---|
| Backend overall | pytest, Hypothesis | ≥ 80% |
| Frontend overall | Jest, fast-check | ≥ 70% |
| Critical paths | Both | ≥ 90% |
| Property tests (dev) | 20 iterations | — |
| Property tests (CI) | 200 iterations | — |

---

## Phase 0 — Backend Test Setup

### Dependencies

```
pytest==8.2.0
pytest-asyncio==0.23.7
hypothesis==6.104.0
faker==25.2.0
pytest-cov==5.0.0
httpx==0.27.0       # For async test client
```

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures: DB session, test client, fake user
├── unit/
│   ├── test_auth.py
│   ├── test_resume_analyzer.py
│   ├── test_recommendation_engine.py
│   ├── test_scraper.py
│   ├── test_career_predictor.py
│   ├── test_bolt_ai.py
│   ├── test_builder_agent.py
│   ├── test_interview_agent.py
│   └── test_linkedin_agent.py
├── property/
│   ├── test_auth_properties.py
│   ├── test_resume_properties.py
│   ├── test_recommendation_properties.py
│   ├── test_agent_properties.py
│   └── test_api_properties.py
└── integration/
    ├── test_api_endpoints.py
    └── test_database.py
```

### Hypothesis Configuration

```python
# conftest.py
from hypothesis import settings

settings.register_profile("ci",  max_examples=200, deadline=None)
settings.register_profile("dev", max_examples=20,  deadline=None)
settings.load_profile("dev")
```

---

## Phase 1 — Frontend Test Setup

### Dependencies

```
jest
@testing-library/react
@testing-library/jest-dom
fast-check           # Property-based testing
msw                  # Mock Service Worker — API mocking
```

### Test Structure

```
src/
├── components/__tests__/
│   ├── Auth.test.tsx
│   ├── Dashboard.test.tsx
│   ├── ResumeBuilder.test.tsx
│   ├── InterviewSession.test.tsx
│   └── BoltWidget.test.tsx
├── services/__tests__/
│   └── api.test.ts
└── utils/__tests__/
    └── helpers.test.ts
```

### fast-check Configuration

```javascript
const testConfig = { numRuns: 100, verbose: true };
```

---

## Property Tests — Complete Reference

All properties tagged: **Feature: ai-internship-career-system, Property {N}: {property_text}**

### Authentication (Properties 1–4)

| # | Property | Requirement |
|---|---|---|
| 1 | Valid registration creates a login-able account | 1.1, 1.2 |
| 2 | Stored password hash never equals plain-text password | 1.4 |
| 3 | Expired JWT tokens are rejected with auth error | 1.3 |
| 4 | Password reset token valid for exactly 1 hour | 1.5 |

```python
# Example
@given(st.emails(), st.text(min_size=8))
def test_registration_enables_login(email, password):
    user = auth_service.register_user(email, password, "Test User")
    token = auth_service.login_user(email, password)
    assert token["access_token"] is not None
```

### Resume (Properties 5–12)

| # | Property |
|---|---|
| 5 | Non-PDF/DOCX files rejected with descriptive error |
| 6 | Re-uploading replaces previous resume (1 per user) |
| 7 | Valid PDF/DOCX produces non-empty extracted text |
| 8 | All structured sections extracted and stored |
| 9 | Skills extracted, normalized, and stored |
| 10 | Resume score always between 0 and 100 |
| 11 | Score increases as more sections are added |
| 12 | Score and feedback persist and are retrievable |

### Scraper (Properties 13–17)

| # | Property |
|---|---|
| 13 | All 4 sources attempted on each scrape run |
| 14 | Every scraped listing includes all required fields |
| 15 | Same title+company+location → UPDATE not INSERT |
| 16 | Failure on one source does not stop others |
| 17 | Minimum 2 seconds between consecutive requests per source |

### Recommendation Engine (Properties 18–21)

| # | Property |
|---|---|
| 18 | All user skills retrieved from DB before vectorizing |
| 19 | User and internship TF-IDF vectors have same dimensionality |
| 20 | Cosine similarity scores within [-1, 1] |
| 21 | Results sorted descending, capped at top 20 |

### Skill Gap & Career (Properties 22–29)

| # | Property |
|---|---|
| 22 | Skill comparison accurately identifies matched and missing |
| 23 | Match % = (matched / total_required) × 100 |
| 24 | Career path count always between 3 and 5 |
| 25 | Each path includes timeline, required skills, alignment score |
| 26 | Paths sorted descending by alignment score |
| 27 | Role comparison accepts 2–4 internship IDs only |
| 28 | Common and unique skills correctly identified |
| 29 | Match % returned for each compared role |

### Application Tracking (Properties 30–33)

| # | Property |
|---|---|
| 30 | New application created with today's date and APPLIED status |
| 31 | Status only updatable to valid states |
| 32 | All user applications returned on retrieval |
| 33 | Notes changes persist and are retrievable |

### Notifications (Properties 34–42)

| # | Property |
|---|---|
| 34 | Email includes internship title, company, and link |
| 35 | At most one email digest per user per day |
| 36 | No emails sent to users with notifications disabled |
| 37 | Failed email retried exactly once after 1 hour |
| 38 | Notification stored with read/unread status |
| 39 | Unread count = count where is_read=false |
| 40 | Viewing a notification sets is_read to true |
| 41 | Notifications older than 30 days auto-deleted |
| 42 | Notifications returned in reverse chronological order |

### Bolt AI (Properties 43–57)

| # | Property |
|---|---|
| 43 | Navigation keywords correctly classified as navigation intent |
| 44 | Session messages preserved and ordered chronologically |
| 45 | Resume coach mode accesses and references user resume data |
| 46 | Skill suggestions reference gaps vs. recommended internships |
| 47 | Score < 70 triggers proactive improvement tip |
| 48 | Job search mode references user recommendations |
| 49 | Career mentor mode references Career Path Predictor results |
| 50 | Career advice includes skills for target paths |
| 51 | Skill advisor accesses and references skill gap data |
| 52 | Skills prioritized by frequency in target job listings |
| 53 | Skills user expresses interest in are tracked |
| 54 | Minimize/expand chat preserves conversation history |
| 55 | All messages logged with user ID and timestamp |
| 56 | Conversation logs retained exactly 90 days |
| 57 | Data deletion removes all associated logs |

### API Security (Properties 58–60)

| # | Property |
|---|---|
| 58 | Unauthenticated > 10/min rejected with 429 |
| 59 | Authenticated > 100/min rejected with 429 |
| 60 | SQL injection and XSS patterns rejected or sanitized |

### Database (Properties 61–62)

| # | Property |
|---|---|
| 61 | Migrations are reversible (apply + rollback = original state) |
| 62 | FK constraint prevents orphaned records |

### Error Handling (Properties 63–66)

| # | Property |
|---|---|
| 63 | All errors display user-friendly messages |
| 64 | All error responses use consistent JSON structure |
| 65 | Errors logged with full stack traces |
| 66 | 5xx errors do not expose implementation details |

### Builder Agent (Properties 67–70)

| # | Property |
|---|---|
| 67 | Session progresses step by step (1→12), never skips |
| 68 | ATS score always between 0 and 100 |
| 69 | Finalize triggers Resume Analyzer and Orchestrator |
| 70 | Resume version number increments monotonically per user |

### Interview Agent (Properties 71–74)

| # | Property |
|---|---|
| 71 | Each session generates exactly 10 questions |
| 72 | Each answer score is between 0 and 10 |
| 73 | Overall score = average of all answer scores × 10 |
| 74 | Readiness level correctly derived from overall score thresholds |

### LinkedIn Agent (Properties 75–77)

| # | Property |
|---|---|
| 75 | Profile score always between 0 and 100 |
| 76 | Score breakdown components sum to profile score |
| 77 | Exactly 3 headline variants returned per analysis |

---

## CI Integration

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: python -m spacy download en_core_web_sm
      - run: pytest --cov --cov-report=xml
      - uses: codecov/codecov-action@v3

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with: { node-version: '18' }
      - run: npm ci
      - run: npm test -- --coverage
      - run: npm run build
```

- All tests run on every PR
- Merges blocked if any tests fail
- Property tests run with 200 iterations in CI
- Coverage reports uploaded to Codecov

---

## Running Tests Locally

```bash
# Backend
pytest                           # All tests, dev profile (20 iterations)
pytest --cov                     # With coverage
pytest tests/unit/               # Unit tests only
pytest tests/property/           # Property tests only
pytest -k "test_auth"            # Specific test by name
hypothesis write tests/property/test_auth_properties.py  # Generate examples

# Frontend
npm test                         # All tests in watch mode
npm test -- --coverage           # With coverage
npm test -- --testPathPattern Auth  # Specific file
```
