# CareerAI — Senior Engineer Onboarding Analysis

> Mental model + improvement strategy, verified against the actual `backend/app` and `frontend/src` source (not just the docs). Line references are to the real code as of this review.

---

## 1. System Overview

**What it is.** CareerAI is a full-stack, AI-driven internship platform for Indian students and fresh graduates. It replaces keyword search with *semantic* matching: resumes and job descriptions are embedded into 384-dim vectors (`all-MiniLM-L6-v2` / `multi-qa-MiniLM`) and compared with pgvector cosine similarity, so a "FastAPI" resume can match a "Python Backend Engineer" role even without the exact keyword. Around that core sit several LLM features (explanations, mock interviews, career paths, LinkedIn optimization, cover letters, a resume builder) powered by Groq LLaMA 3.1.

**Who the user is.** A student/fresh grad who uploads a resume, gets ranked internship recommendations with explanations, then uses the surrounding tools to close skill gaps, prep interviews, and track applications.

**Core user flow.**
1. Register / login → JWT stored in `localStorage`.
2. Upload PDF resume → stored in Supabase → text extracted (pdfplumber) → Groq extracts skills → skills saved → resume embedded.
3. Scraper ingests internships (LinkedIn / Internshala / Shine) → each embedded on insert.
4. Internships page → `POST /recommendations/refresh` runs the engine → pgvector prefilter + multi-signal scoring → cards show "% Match".
5. Search → real-time query embedding → cards show "% Relevant".
6. "Why this matches you?" → Groq returns match reasons, missing skills, a tip.
7. Career Paths, Interview Prep, LinkedIn Analyzer, Applications Tracker, Bolt AI chatbot.

---

## 2. Architecture Breakdown

Two agent systems coexist and should not be confused:

**A. The "4-agent" pipeline in the architecture doc (Skill / Job / Matching / Explanation) is a TARGET design — it is NOT implemented.** Today the equivalent logic lives inline in `services/recommendation_engine.py` as a single multi-signal scorer. This is the refactor the architecture guide is proposing.

**B. The ReAct orchestrator that DOES exist** (`orchestrator/runner.py`, wired to `POST /api/agent/trigger` as a background task) coordinates four real, LLM-backed agents:

| Agent | File | Responsibility |
|---|---|---|
| Scout | `agents/scout_agent.py` | Runs the scraper, LLM-scores listing relevance |
| Analyst | `agents/analyst_agent.py` | Computes skill-frequency trends, saves `SkillSnapshot`, LLM insight |
| Coach | `agents/coach_agent.py` | Generates weekly nudges from activity/resume score |
| Writer | `agents/writer_agent.py` | Cover letters — invoked only via `POST /drafts/generate`, NOT by the orchestrator loop (`dispatcher.py` raises on "writer") |

The orchestrator loop (`runner.py:46`) lets the LLM choose scout|analyst|coach|done for up to 10 iterations, logging each `AgentRun` and persisting shared state via `StateManager` (PostgreSQL).

**Where recommendations come from:** `recommendation_engine.py` → pgvector cosine prefilter + a weighted 5-signal composite. **Where scoring happens:** same file (see §3/§6). Explanations come from Groq via the explain endpoints.

---

## 3. Backend Understanding

Everything the documentation lists exists on disk and is mounted under `/api` in `main.py`. Highlights and data shapes:

- **`GET /recommendations`** → cached rows from DB; each item carries `match_percentage`, `similarity_score`, and a re-derived `display_score` + label.
- **`POST /recommendations/refresh`** → runs the full engine and persists top matches.
- **`GET /recommendations/skill-gap`** → aggregate gap across top-N recs *(exists — undocumented)*.
- **`POST /recommendations/explain/{id}`** → LLM explanation *(note: path is `/explain/{id}`, not `/explain`)*.
- **`GET /internships/{id}/skill-gap`** → `{ required, matched, missing, match_percentage }` where `match_percentage = matched/required * 100` (raw ratio, un-normalized).
- **`GET /internships/{id}/explain`** → `{ match_reasons[], missing_skills[], tip }`.
- **`GET /career/paths`** → ranked archetypes with `salary_range`, `growth_rate`, `open_positions`, `why_fits`, `top_skill_to_learn` (LLM-decorated; defaults hardcoded).
- **`/interview/*`** (8 endpoints), **`/linkedin/*`** (6), **`/applications/*`** (5), **`/resumes/*`** + **`/resume/{id}/analysis`**, **`/resume-agent/*`** (13, incl. templates/preview/ats-score/export), **`/bolt/*`**, **`/agent/*`**, **`/notifications/*`**, **`/drafts/*`** (cover letters).

**Already implemented (confirmed real, not stubs):** recommendation engine, embedding service (+ cache singleton), resume analyzer (ATS scoring), career path predictor, interview generator/evaluator/report, LinkedIn profile scorer + gap analyzer + content optimizer, Bolt chatbot, resume builder service + export, all four orchestrator agents, cover-letter writer.

**Thinner than they look:** career path "prediction" is exact-string skill overlap against a static 7-role catalog (`career_path_predictor.py:164`); salary/growth/open-positions are hardcoded defaults (`₹6-20 LPA`, `+18%`, `12000`) unless the LLM overrides them.

---

## 4. Frontend Understanding

React 18 + TS + Vite + Tailwind + a full shadcn/ui component set. Axios instance in `lib/api.ts` attaches the JWT; all API functions live in `lib/services.ts`.

| Page | Purpose | Wiring status |
|---|---|---|
| Dashboard | Stats, charts, activity | **Partly faked**: application-trend chart hardcoded; skill proficiency = `Math.random()`; `resumeScore` set but never rendered |
| ResumeAnalyzer | Upload + ATS score + skills | Wired; relies on a fixed 3s `setTimeout` instead of a status poll |
| Internships | Recommendations + search | Wired but heavy client massaging; "tags" faked by splitting description; bookmarks localStorage-only |
| CareerPaths | Career prediction | Wired to `getPaths()`; roadmap hardcoded fallback; `missingSkills` mapped but **never rendered** |
| ApplicationsTracker | Kanban | Status change/delete wired; "Add Application"/"Add Card" buttons dead; drag-drop cosmetic only |
| InterviewPrep | Mock interviews | Largely wired; category counts + stats heuristic; "AI Coach" = Coming Soon |
| LinkedInAnalyzer | Profile analysis | Wired to `analyze`; sends placeholder experience/skills; network + growth stats hardcoded fake; `getLatest` is dead code |
| ResumeBuilder | Conversational builder | Hidden from sidebar; `getTemplates()` **doesn't exist in services.ts** → always falls back to hardcoded templates; toolbar buttons dead |

**Data flow:** pages → `services.ts` functions → Axios → FastAPI. Internships rebuilds its list entirely from the recommendations response to avoid "0% Match" cards.

---

## 5. Current Strengths

- **Semantic core is genuinely good** — pgvector + sentence-transformers, embeddings normalized, prefilter then score. This is the right architecture and it works.
- **Breadth of real backend** — ~14 routers, ~25 services, all backed by code. Interview, LinkedIn, cover-letter, and resume-builder pipelines are real LLM features, not mockups.
- **A working multi-agent orchestrator** with ReAct loop, dispatch, persisted state, and run logging — rare in projects this size.
- **Clean separation** — routes / services / agents / schemas / models are well organized; `dependencies.py` solves the circular-import cleanly.
- **Explainability** — every recommendation can produce structured LLM reasons + missing skills + tip.

---

## 6. Current Gaps / Problems

**#1 — Scoring is inconsistent across THREE computations (highest priority).**
1. *Engine (write path)* `recommendation_engine.py:274`: `composite = semantic*.30 + coverage*.25 + depth*.20 + domain*.15 + seniority*.10`; `match_percentage = composite*100`. Skill match = embedding cosine ≥ 0.70.
2. *Recommendations read path* `routes/recommendations.py:38`: re-normalizes that percentage through `normalize_score(..., max_val=0.85)` into a **compressed 50–100 band**, then applies a **different** label threshold set (88/78/68/58), and recomputes matched/missing with **exact string intersection**.
3. *`/internships/{id}/skill-gap`*: exact intersection, **raw 0–100** ratio, no normalization.

Consequences a user actually sees: the same internship can read "82%" on the card and "40%" on the skill-gap view; a completely unrelated job still shows ≥50% because of the display floor; and the score (semantic) disagrees with the matched/missing lists (exact string), so an "Excellent" match can still list skills as "missing." The engine even computes a label that is then thrown away.

**#2 — Skill-gap has backend, zero frontend.** Two skill-gap endpoints exist; no service function, no page, no UI consumes them. `CareerPaths` even maps `missingSkills` then never renders it.

**#3 — Faked/cosmetic surfaces.** Dashboard trends + skill %, LinkedIn network/growth stats, ResumeBuilder templates, several dead buttons.

**#4 — Broken calls / path mismatches.** `resumeBuilderService.getTemplates()` not defined (silently swallowed); `/resume/{id}/analysis` singular vs `/resumes/` plural — verify; raw `POST /agent/trigger` calls bypass the service layer.

**#5 — Architecture-doc items still missing:** no agent-based recommendation refactor, no Redis cache, no per-dimension confidence surfaced to UI, no feedback loop, no job alerts.

---

## 7. Feature Readiness Mapping (backend → frontend)

| Feature | Backend | Frontend | Verdict |
|---|---|---|---|
| Recommendations | ✅ engine | ✅ Internships | Working, needs scoring cleanup + polish |
| Explainable match | ✅ `/explain` | ✅ inline expander | Working |
| Resume ATS scoring | ✅ analyzer | ⚠️ shown, but skill % faked | Partial UI |
| Skill Gap | ✅ 2 endpoints | ❌ none | **Backend ✅ / Frontend ❌** |
| Career Paths | ✅ (rule-based + LLM) | ⚠️ renders, missingSkills unused | Partial |
| Interview Prep | ✅ full | ✅ wired, coach stub | Working |
| LinkedIn Analyzer | ✅ full | ⚠️ placeholders + fake stats | Partial |
| Applications Tracker | ✅ CRUD | ⚠️ dead add buttons, fake DnD | Partial |
| Resume Builder | ✅ 13 endpoints | ⚠️ hidden, getTemplates broken | Partial/hidden |
| Cover Letter (Writer) | ✅ `/drafts` | ❌ none | **Backend ✅ / Frontend ❌** |
| Job Alerts | ❌ | ❌ | Missing both |
| Resume Improver | ✅ `resume_optimizer` service | ❌ no dedicated UI | Backend partial / Frontend ❌ |

---

## 8. Execution Plan (phased)

**Guiding principle:** fix the data-truth problems (scoring) before building new surfaces on top of them, otherwise every new feature inherits the inconsistency.

### Week 1 — Trust the numbers + expose what already exists
1. **Unify scoring (do first — everything depends on it).**
   - Pick ONE canonical score + label definition. Recommend: keep the engine's composite as the source of truth, decide raw-vs-display once, remove the second normalization + second label set in `routes/recommendations.py`.
   - Make matched/missing use the SAME definition as the score (either semantic ≥0.70 everywhere, or exact everywhere — not mixed).
   - Files: `services/recommendation_engine.py` (`:274`, `:638`, `:725`, `:771`), `routes/recommendations.py` (`:38`, `:55`, `:84`), `routes/internships.py` (`:169`), `services/embedding_service.py` (`normalize_score` `:110`). Frontend read: `Internships.tsx:184,207,531`.
2. **Skill Gap page (backend done, build UI).**
   - Add `internshipService.getSkillGap(id)` → `GET /internships/{id}/skill-gap`; new page + route + sidebar entry; render matched/missing/coverage. Reuse in CareerPaths for the already-mapped `missingSkills`.
   - Files: `lib/services.ts`, `pages/SkillGap.tsx` (new), `app/routes.ts`, `Sidebar.tsx`, `CareerPaths.tsx:107`.
3. **Recommendation UX polish.**
   - Replace faked description-split "tags" with real matched skills from the API; fix "High Match" stat during search mode; clear `searchScores` on exit; consistent color thresholds.
   - Files: `Internships.tsx` (`:159`, `:485`, `:532`, `:546`).
   - *Depends on #1.*

### Week 2 — Retention features
4. **Job Alerts** (net-new both ends): notification generation when a new internship scores above a threshold for a user; consume via existing `/notifications`. Files: new service + scheduled trigger, `agents/scout_agent.py` hook, `notification_service.py`, frontend `Topbar.tsx`/notifications UI. *Depends on #1 (needs trustworthy scores).* 
5. **Application Tracker fixes**: wire "Add Application"/"Add Card" handlers, real drag-and-drop, reconcile timeline statuses with columns. Files: `ApplicationsTracker.tsx` (`:90`, `:215`, `:254`), `applicationService`.
6. **Resume Improver UI**: expose the existing `resume_optimizer` service via a route (if not already) + a UI action on ResumeAnalyzer. Files: `services/resume_optimizer.py`, `routes/resume_analysis.py` or `resume.py`, `ResumeAnalyzer.tsx`.

### Week 3 — LLM-forward features
7. **Interview Prep**: replace "AI Coach" stub / heuristic stats with real values from `/interview/report` + `/interview/history`. Files: `InterviewPrep.tsx` (`:10`, `:64`, `:433`).
8. **Cover Letter Generator UI** (Writer agent + `/drafts` already exist): build the page consuming `POST /drafts/generate` and the drafts CRUD. Files: new `pages/CoverLetters.tsx`, `lib/services.ts`, `routes.ts`, `Sidebar.tsx`.
9. **Career Path Suggestions polish**: render `missingSkills`, replace hardcoded roadmap/salary defaults with LLM output where available, label rule-based numbers honestly. Files: `career_path_predictor.py`, `career_ai_service.py`, `CareerPaths.tsx`.

### Cross-cutting dependencies
- Scoring unification (#1) blocks recommendation polish (#3) and job alerts (#4).
- Skill Gap UI (#2) shares skill-matching logic with the scoring fix — do #1 and #2 together.
- Cover-letter and skill-gap are the two "backend-ready, frontend-missing" quick wins; sequence them early for visible progress.
- Fix broken plumbing opportunistically: `resumeBuilderService.getTemplates()` missing (`ResumeBuilder.tsx:41` / `services.ts`), verify `/resume/{id}/analysis` path.

---

*Prepared for implementation via Claude Code. No code changed in this pass — analysis only.*
