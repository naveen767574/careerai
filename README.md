# CareerAI — An AI-Driven Multi-Agent Framework for Personalized Internship Recommendation and Career Path Prediction

<div align="center">

![CareerAI Banner](https://img.shields.io/badge/CareerAI-AI%20Powered-brightgreen?style=for-the-badge&logo=robot)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18.1-336791?style=for-the-badge&logo=postgresql)
![Groq](https://img.shields.io/badge/Groq-LLaMA%203.1-orange?style=for-the-badge)

**A multi-agent AI platform that automates internship discovery, skill gap analysis, and career guidance for students.**

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Semantic Search** | Vector embeddings with pgvector for intelligent job matching |
| 🤖 **Explainable AI** | "Why this matches you?" — LLM explains each recommendation |
| 📊 **Career Paths** | AI predicts career paths with India-specific salary data |
| 📄 **Resume Analyzer** | Upload PDF → AI extracts skills + ATS score |
| 🎯 **Interview Prep** | AI generates personalized questions + evaluates answers |
| 💼 **LinkedIn Analyzer** | AI analyzes and optimizes your LinkedIn profile |
| 📋 **Applications Tracker** | Kanban board to track all job applications |
| 💬 **Bolt AI** | Draggable AI career assistant with moving eyes |

---

## 🏗️ Architecture

```
User uploads resume
      ↓
Skills extracted → Embeddings generated (sentence-transformers)
      ↓
Compared with 123+ internship embeddings via pgvector
      ↓
Top matches ranked by cosine similarity
      ↓
Groq LLaMA 3.1 explains each match in human language
      ↓
Career paths predicted with Indian market data
      ↓
Interview questions generated per internship
      ↓
Answers evaluated and scored by AI
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, TypeScript, Tailwind CSS, Framer Motion |
| **Backend** | FastAPI, Python 3.11, SQLAlchemy, Alembic |
| **Database** | PostgreSQL 18.1 + pgvector extension |
| **AI/LLM** | Groq API (LLaMA 3.1-8b-instant) — FREE |
| **Embeddings** | sentence-transformers (multi-qa-MiniLM-L6-cos-v1) |
| **Scraping** | BeautifulSoup4 — LinkedIn, Internshala, Shine |
| **Storage** | Supabase Storage |
| **Auth** | JWT + bcrypt |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 18+ with pgvector extension
- Git

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/careerai.git
cd careerai
```

### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your API keys

# Setup database
createdb ai_career_dev
psql ai_career_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run migrations
alembic upgrade head

# Start backend
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Setup environment variables
cp .env.example .env

# Start frontend
npm run dev
```

### 4. Open in browser
```
http://localhost:5173
```

---

## 🔑 Environment Variables

### Backend (.env)
| Variable | Description | Where to get |
|----------|-------------|--------------|
| `DATABASE_URL` | PostgreSQL connection string | Local PostgreSQL |
| `JWT_SECRET` | Secret key for JWT tokens | Generate random string |
| `GROQ_API_KEY` | Groq LLM API key | [console.groq.com](https://console.groq.com) (FREE) |
| `SUPABASE_URL` | Supabase project URL | [supabase.com](https://supabase.com) |
| `SUPABASE_SERVICE_KEY` | Supabase service key | Supabase dashboard |

### Frontend (.env)
| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API URL (default: http://localhost:8000/api) |

---

## 📁 Project Structure

```
careerai/
├── backend/
│   ├── app/
│   │   ├── models/          # Database models
│   │   ├── routes/          # API endpoints
│   │   ├── services/        # Business logic + AI services
│   │   ├── scraper/         # Job scrapers (LinkedIn, Internshala, Shine)
│   │   ├── schemas/         # Pydantic schemas
│   │   └── main.py          # FastAPI app entry point
│   ├── alembic/             # Database migrations
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Environment template
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/  # Reusable UI components
│   │   │   ├── pages/       # All 8 pages
│   │   │   └── lib/         # API services
│   ├── package.json         # Node dependencies
│   └── .env.example         # Environment template
└── README.md
```

---

## 🤖 AI Models Used

| Model | Purpose | Cost |
|-------|---------|------|
| `groq/llama-3.1-8b-instant` | Match explanations, career insights, interview Q&A | FREE |
| `multi-qa-MiniLM-L6-cos-v1` | Semantic embeddings (384-dim) | FREE (local) |
| `pgvector` | Vector similarity search | FREE (PostgreSQL extension) |

> **Note:** The sentence-transformer model (~80MB) downloads automatically on first run from HuggingFace.

---

## 📊 Algorithms

- **Cosine Similarity** — Resume-to-job matching via vector embeddings
- **Approximate Nearest Neighbor** — pgvector for fast vector search
- **TF-IDF** — Fallback keyword matching
- **ReAct** — Multi-agent orchestration pattern
- **Score Normalization** — Maps raw similarity scores to display percentages

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | User login |
| POST | `/api/auth/register` | User registration |
| GET | `/api/internships` | List internships with semantic search |
| GET | `/api/internships/{id}/explain` | AI match explanation |
| GET | `/api/recommendations` | Personalized recommendations |
| GET | `/api/career/paths` | AI career path predictions |
| POST | `/api/interview/start` | Start mock interview session |
| POST | `/api/linkedin/analyze` | Analyze LinkedIn profile |
| POST | `/api/bolt/chat` | Chat with Bolt AI |

---

## 👨‍💻 Author

**Naveen B**
- LinkedIn: [linkedin.com/in/naveen-b-profile](https://www.linkedin.com/in/naveen-b-profile/)
- GitHub: [https://github.com/naveenb-ai](https://github.com/naveenb-ai)

---

## 📄 License

This project is licensed under the MIT License.

---

<div align="center">
Built with ❤️ using FastAPI + React + Groq AI
</div>
