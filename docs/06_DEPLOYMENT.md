# Deployment Guide
## AI-Powered Internship & Career Recommendation System

> Phase-by-phase deployment, CI/CD, and infrastructure reference.
> Stack: Vercel (frontend) · Render/Railway (backend) · Supabase/Neon (database) · Cloudflare R2 (files)

---

## Infrastructure Overview

```
Users
  │
  ▼
Vercel CDN — React Frontend (auto-deploy from main)
  │  HTTPS/REST API
  ▼
Render / Railway — FastAPI Backend
  │  Cron: 0 */6 * * * (Orchestrator)
  │  PostgreSQL connection (SSL required)
  ▼
Supabase / Neon — PostgreSQL 15+
  │  PgBouncer connection pooling
  │  Daily automated backups
  │  7-day point-in-time recovery
  ▼
Cloudflare R2 — File Storage
  S3-compatible, no egress fees
  Resumes + exported PDFs/DOCXs
```

---

## Phase 0 — Local Development Setup

### Prerequisites

```bash
# Backend
python 3.11+
postgresql 15+ (local or Supabase dev)
node 18+ (for npm)

# Install backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Run backend
uvicorn app.main:app --reload --port 8000

# Install frontend
cd frontend
npm install

# Run frontend
npm run dev
```

### `.env` File (Backend)

```
DATABASE_URL=postgresql://user:password@localhost:5432/ai_career_dev
JWT_SECRET=your_dev_secret_here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
OPENAI_API_KEY=sk-...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@email.com
SMTP_PASSWORD=your_app_password
FRONTEND_URL=http://localhost:5173
RATE_LIMIT_ENABLED=false
LOG_LEVEL=DEBUG
R2_ACCESS_KEY=your_r2_key
R2_SECRET_KEY=your_r2_secret
R2_BUCKET_NAME=ai-career-dev
R2_ENDPOINT=https://[account-id].r2.cloudflarestorage.com
```

### Database Init (Local)

```bash
alembic upgrade head                 # Run all migrations
python scripts/seed_data.py         # Optional: seed sample internships
```

---

## Phase 1 — Database Deployment (Supabase)

### Setup

1. Create account at supabase.com
2. Create new project → note the connection string
3. Enable PgBouncer connection pooling in project settings
4. Set `DATABASE_URL` to the pooler connection string (port 6543)

```
postgresql://postgres:[password]@[host]:6543/postgres?sslmode=require
```

### Configuration

| Setting | Value |
|---|---|
| PostgreSQL version | 15+ |
| Connection pooling | PgBouncer (enabled) |
| SSL mode | Required |
| Max connections | 100 |
| Automated backups | Daily |
| Point-in-time recovery | 7 days |

### Database Initialization (Production)

```bash
# Set DATABASE_URL env var to production connection string
alembic upgrade head
```

---

## Phase 2 — File Storage (Cloudflare R2)

### Setup

1. Create Cloudflare account → R2 → Create bucket: `ai-career-prod`
2. Create API token with R2 read/write permissions
3. Note: Account ID, Access Key, Secret Key

### File Organization

```
ai-career-prod/
├── resumes/{user_id}/{filename}_{timestamp}
└── exports/{user_id}/{type}/{filename}_{timestamp}.pdf|docx
```

### Backend R2 Client

```python
import boto3

s3 = boto3.client(
    's3',
    endpoint_url=f'https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
    aws_access_key_id=settings.R2_ACCESS_KEY,
    aws_secret_access_key=settings.R2_SECRET_KEY,
)

def upload_file(file_obj, key: str) -> str:
    s3.upload_fileobj(file_obj, settings.R2_BUCKET_NAME, key)
    return key

def get_signed_url(key: str, expires_in: int = 3600) -> str:
    return s3.generate_presigned_url('get_object',
        Params={'Bucket': settings.R2_BUCKET_NAME, 'Key': key},
        ExpiresIn=expires_in
    )
```

---

## Phase 3 — Backend Deployment (Render)

### `render.yaml`

```yaml
services:
  - type: web
    name: ai-career-backend
    env: python
    region: oregon
    plan: starter
    buildCommand: "pip install -r requirements.txt && python -m spacy download en_core_web_sm"
    startCommand: "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: JWT_SECRET
        generateValue: true
      - key: JWT_ALGORITHM
        value: HS256
      - key: JWT_EXPIRATION_HOURS
        value: "24"
      - key: OPENAI_API_KEY
        sync: false
      - key: SMTP_HOST
        sync: false
      - key: SMTP_PORT
        value: "587"
      - key: SMTP_USERNAME
        sync: false
      - key: SMTP_PASSWORD
        sync: false
      - key: FRONTEND_URL
        sync: false
      - key: RATE_LIMIT_ENABLED
        value: "true"
      - key: LOG_LEVEL
        value: INFO
      - key: R2_ACCESS_KEY
        sync: false
      - key: R2_SECRET_KEY
        sync: false
      - key: R2_BUCKET_NAME
        sync: false
      - key: R2_ENDPOINT
        sync: false

  - type: cron
    name: orchestrator-cron
    env: python
    schedule: "0 */6 * * *"
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python -m app.orchestrator.run_cron"
    envVars:
      - fromGroup: ai-career-env
```

### Environment Variable Groups (Render)

Create an env group called `ai-career-env` in Render dashboard with all shared variables so both the web service and cron job can reference them.

### Post-Deploy Hook

After each deploy, run migrations automatically:

```bash
# Add to startCommand or as a pre-start script
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## Phase 4 — Frontend Deployment (Vercel)

### `vercel.json`

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }],
  "env": {
    "VITE_API_URL": "@api_url",
    "VITE_APP_NAME": "AI Career Platform"
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options",        "value": "DENY" },
        { "key": "X-XSS-Protection",       "value": "1; mode=block" }
      ]
    }
  ]
}
```

### Vercel Setup

1. Connect GitHub repo to Vercel
2. Set environment variables in Vercel dashboard:
   - `VITE_API_URL` = `https://your-backend.onrender.com`
   - `VITE_APP_NAME` = `AI Career Platform`
3. Automatic deploys trigger on push to `main`
4. Preview deploys created for every pull request

---

## Phase 5 — CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

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
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          python -m spacy download en_core_web_sm
      - name: Run tests
        run: |
          cd backend
          pytest --cov --cov-report=xml
        env:
          DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}
          JWT_SECRET: test_secret
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      - uses: codecov/codecov-action@v3

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with: { node-version: '18' }
      - run: cd frontend && npm ci
      - run: cd frontend && npm test -- --coverage
      - run: cd frontend && npm run build

  deploy:
    needs: [test-backend, test-frontend]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy backend to Render
        run: curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK }}"
      - name: Deploy frontend to Vercel
        run: |
          npm install -g vercel
          cd frontend && vercel --prod --token=${{ secrets.VERCEL_TOKEN }}
```

### Required GitHub Secrets

| Secret | Value |
|---|---|
| `TEST_DATABASE_URL` | PostgreSQL test DB connection string |
| `OPENAI_API_KEY` | OpenAI API key |
| `RENDER_DEPLOY_HOOK` | Render deploy hook URL |
| `VERCEL_TOKEN` | Vercel API token |

---

## Deployment Workflow

### Standard Deploy (Most Common)

```
1. Write code on feature branch
2. Open pull request → CI runs automatically
3. Tests pass → merge to main
4. CI/CD deploys backend (Render) + frontend (Vercel) automatically
5. Run: alembic upgrade head (if schema changed)
6. Check /health endpoint: {"status": "healthy"}
7. Verify critical features in production
```

### Emergency Rollback

```bash
# Backend (Render): use Render dashboard → Deploys → Rollback
# Frontend (Vercel): use Vercel dashboard → Deployments → Promote previous

# Database rollback (if migration went wrong)
alembic downgrade -1              # Rollback one migration
alembic downgrade <revision_id>   # Rollback to specific revision
```

---

## Monitoring & Observability

### Health Check

```
GET /health
→ {"status": "healthy", "timestamp": "...", "database": "connected", "version": "1.0.0"}
Polled every 30 seconds by Render
```

### Logging

- Structured JSON format
- All errors logged with: timestamp, user_id, endpoint, duration, stack trace
- Free tier: 7-day retention | Paid tier: 30+ days

### Optional Monitoring Stack

```
Sentry     — Error tracking and alerting
New Relic  — Performance monitoring and APM
Datadog    — Infrastructure metrics
```

### Key Metrics to Monitor

| Metric | Alert Threshold |
|---|---|
| API response time (p95) | > 2000ms |
| Error rate per endpoint | > 1% |
| Database query time | > 500ms |
| Scraper success rate | < 75% |
| Recommendation generation | > 5000ms |
| Agent run failures | Any |

---

## Backup & Disaster Recovery

### Database Backups (Supabase)

- Automated daily backups (retained 7 days free, 30 days paid)
- Point-in-time recovery: restore to any moment in the last 7 days
- Manual backup: `pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql`

### Recovery Procedure

```
1. Detect issue via /health check or monitoring alert
2. Check Render logs for backend errors
3. Check Supabase dashboard for DB issues
4. Decision:
   a. Code bug → Rollback backend deploy on Render
   b. Migration issue → alembic downgrade -1 → fix → re-migrate
   c. Data corruption → Restore from Supabase point-in-time recovery
5. Verify /health returns healthy
6. Verify critical endpoints (auth, resume, recommendations)
7. Post-mortem: document root cause and prevention
```

---

## Cost Estimates

| Tier | Services | Monthly Cost |
|---|---|---|
| **MVP (Free)** | Vercel Hobby + Render Free + Supabase Free (500MB) + Cloudflare R2 Free (10GB) | **$0** |
| **Production** | Vercel Pro ($20) + Render Starter ($25) + Supabase Pro ($25) + OpenAI (~$30-100) + SendGrid ($15) | **$115–185** |
| **Scale** | Vercel Pro + Render Standard ($85) + Supabase Pro + higher OpenAI + Redis ($15) | **$300–600** |

### Free Tier Limits

| Service | Free Limit |
|---|---|
| Vercel Hobby | 100GB bandwidth/month |
| Render Free | 750 hours/month, spins down after 15min inactivity |
| Supabase Free | 500MB database, 1GB file storage |
| Cloudflare R2 Free | 10GB storage, 1M read ops/month |
| OpenAI | None — pay per token |

**Note**: Render free tier spins down after 15 minutes of inactivity — first request takes ~30 seconds to wake up. Upgrade to Starter ($25/month) for always-on behavior in production.

---

## Availability Target

- **99% uptime** during business hours
- Deployments complete within 10 minutes
- Zero data loss on all deployments
- Recovery time objective (RTO): < 30 minutes
- Recovery point objective (RPO): < 24 hours (daily backup granularity)
