# Agents Implementation Guide
## AI-Powered Internship & Career Recommendation System

> Phase-by-phase agent development reference.
> All agents use OpenAI GPT-4 for reasoning. All communicate via Orchestrator only.

---

## Agent Overview

| # | Agent | Module | Trigger |
|---|---|---|---|
| 0 | Orchestrator | `app/orchestrator/` | Cron / events / user actions |
| 1 | Scout | `app/scout_agent/` | Every 6h + on-demand |
| 2 | Analyst | `app/analyst_agent/` | Post-Scout + weekly |
| 3 | Coach | `app/coach_agent/` | Post-Analyst + on login |
| 4 | Writer | `app/writer_agent/` | Per listing / on-demand |
| 5 | Builder | `app/resume_agent/` | User selects "Create Resume" |
| 6 | Interview | `app/interview_agent/` | Per application / on-demand |
| 7 | LinkedIn | `app/linkedin_agent/` | On-demand + Coach nudge |

**Core principle**: Agents do NOT call each other. All coordination goes through the Orchestrator via `agent_state` and `agent_runs`.

---

## Phase 0 — Orchestrator Agent

### Purpose

Coordinates the agent system. Reads shared state, decides which agent to invoke next, dispatches, reads output, and updates state.

### Structure

```
app/orchestrator/
├── __init__.py
├── runner.py          # Main orchestrator loop
├── dispatcher.py      # Routes to the right agent
├── state_manager.py   # Load/save agent_state
└── schemas.py         # AgentState, AgentAction dataclasses
```

### ReAct Loop

```python
# app/orchestrator/runner.py
def orchestrator_loop(user_id: int, trigger: str):
    state = state_manager.load(user_id)
    state["trigger"] = trigger
    state["done"] = False

    while not state["done"]:
        # Reason: what should happen next?
        thought = llm.reason(state)

        # Decide: which agent to invoke?
        action = llm.decide_action(thought)

        if action == "done":
            state["done"] = True
            break

        # Act: run that agent
        log_run(user_id, action, "running")
        result = dispatcher.dispatch(action, state)
        log_run(user_id, action, "success", result)

        # Observe: update state with result
        state = state_manager.update(state, action, result)
        state_manager.save(user_id, state)
```

### LLM System Prompt (Orchestrator)

```
You are an orchestration agent managing a career assistance system.
Given the current state, decide which sub-agent to invoke next.

Current state: {state_json}
Trigger: {trigger}

Available agents: scout | analyst | coach | writer | done

Respond with a JSON object: {"thought": "...", "action": "agent_name_or_done"}

Rules:
- After cron/scrape trigger: always run scout first, then analyst, then coach
- After user resume upload: run analyst, then coach
- After user resume builder complete: run analyst, then coach
- If all relevant agents have run: action = "done"
```

### Trigger Sources

| Trigger | Action Sequence |
|---|---|
| `cron_6h` | scout → analyst → coach |
| `resume_upload` | analyst → coach |
| `resume_builder_complete` | analyst → coach |
| `user_refresh` | scout → analyst |
| `manual` | Full sequence |

### Agent Control API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/agent/trigger` | Manually trigger Orchestrator |
| GET | `/api/agent/status` | Current state + last run |
| GET | `/api/agent/runs` | Run history |
| GET | `/api/agent/runs/:id` | Run detail (input, output, duration) |

### Phase 0 Checklist

- [ ] `agent_state` and `agent_runs` tables exist
- [ ] `state_manager.load/save` working
- [ ] Orchestrator loop runs without error
- [ ] `agent_runs` log populated after each dispatch
- [ ] Cron job configured in `render.yaml`: `0 */6 * * *`
- [ ] Manual trigger endpoint returns 200

---

## Phase 1 — Scout Agent

### Purpose

Elevates the web scraper into an agent. Doesn't just collect listings — reasons about fit for each user and scores/ranks them.

### Structure

```
app/scout_agent/
├── __init__.py
├── scout_runner.py      # Main entry point called by Orchestrator
├── scorer.py            # LLM-powered per-user listing scoring
└── schemas.py           # ScoutOutput dataclass
```

### Key Methods

```python
class ScoutAgent:
    def run(user_id: int, state: dict) -> ScoutOutput:
        # 1. Scrape all sources (reuse scraper module)
        listings = scraper.scrape_all_sources()

        # 2. For each new listing: score against user profile
        scored = [self.score_listing(listing, user_profile) for listing in listings]

        # 3. Filter: only return listings scoring > 0.4
        top_matches = [l for l in scored if l.score > 0.4][:20]

        # 4. Upsert listings to DB
        # 5. Store top matches in agent state for Analyst
        return ScoutOutput(top_matches=top_matches, total_scraped=len(listings))

    def score_listing(listing: Internship, user_profile: UserProfile) -> ScoredListing:
        # LLM reasons: "Is this listing worth surfacing for this user? Why?"
        # Returns score (0-1) + rationale string
```

### LLM Scoring Prompt

```
You are evaluating whether a job listing is relevant for a specific user.

User profile:
- Skills: {user_skills}
- Career interests: {career_interests}
- Experience level: {experience_level}

Job listing:
- Title: {title}
- Company: {company}
- Required skills: {required_skills}
- Description excerpt: {description[:300]}

Score the relevance from 0.0 to 1.0 and explain why in one sentence.
Respond as JSON: {"score": 0.0-1.0, "rationale": "..."}
```

### Phase 1 Checklist

- [ ] ScoutAgent integrates with existing scraper
- [ ] LLM scores each listing per user (not just TF-IDF)
- [ ] Top matches stored in `recommendations` table
- [ ] `agent_runs` log entry created with input/output JSON
- [ ] Scout output passed to Orchestrator state for Analyst

---

## Phase 2 — Analyst Agent

### Purpose

Tracks skill gap evolution over time. Saves weekly snapshots. Detects momentum — which skills are rising in demand for this user's target roles.

### Structure

```
app/analyst_agent/
├── __init__.py
├── analyst_runner.py    # Main entry point
├── snapshot_manager.py  # Save and compare skill snapshots
├── trend_detector.py    # Rising / stable / falling classification
└── schemas.py           # AnalystOutput, SkillTrend dataclasses
```

### Key Methods

```python
class AnalystAgent:
    def run(user_id: int, state: dict) -> AnalystOutput:
        # 1. Get current skill frequency from Scout's top matches
        current_freq = self.calculate_skill_frequency(state["scout_top_matches"])

        # 2. Load last week's snapshot
        previous = snapshot_manager.load_latest(user_id)

        # 3. Compare: detect trend direction per skill
        trends = trend_detector.detect(current_freq, previous)

        # 4. Save new snapshot to skill_snapshots table
        snapshot_manager.save(user_id, current_freq, trends)

        # 5. Generate LLM insight summary
        insight = self.generate_insight(trends, user_profile)

        return AnalystOutput(trends=trends, insight=insight)

    def generate_insight(trends, profile) -> str:
        # LLM generates 2-3 natural language insights
        # e.g. "Docker appeared in 68% of your top matches this week, up from 40%"
```

### Trend Classification

```python
def classify_trend(current_pct: float, previous_pct: float) -> str:
    delta = current_pct - previous_pct
    if delta > 10:   return "rising"
    if delta < -10:  return "falling"
    return "stable"
```

### Skill Snapshot API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/skills/snapshots` | All snapshots (for trend chart) |
| GET | `/api/skills/trends` | Latest trend report |

### Phase 2 Checklist

- [ ] `skill_snapshots` table populated after each run
- [ ] Trend direction detected per skill
- [ ] LLM insight summary generated and stored
- [ ] Skill dashboard data available via API
- [ ] Analyst output passed to Orchestrator state for Coach

---

## Phase 3 — Coach Agent

### Purpose

Synthesizes Scout + Analyst outputs into proactive, personalized coaching. Detects inactivity. Generates briefs without the user asking.

### Structure

```
app/coach_agent/
├── __init__.py
├── coach_runner.py      # Main entry point
├── brief_generator.py   # LLM-powered coaching brief
├── inactivity_detector.py
└── schemas.py           # CoachingBrief dataclass
```

### Key Methods

```python
class CoachAgent:
    def run(user_id: int, state: dict) -> CoachingBrief:
        # 1. Gather all context
        context = {
            "scout_matches": state["scout_top_matches"],
            "skill_trends": state["analyst_trends"],
            "analyst_insight": state["analyst_insight"],
            "application_activity": self.get_recent_activity(user_id),
            "resume_score": self.get_resume_score(user_id),
            "career_paths": self.get_career_paths(user_id),
        }

        # 2. Detect inactivity
        days_inactive = self.days_since_last_application(user_id)

        # 3. Generate brief via LLM
        brief = brief_generator.generate(context, days_inactive)

        # 4. Store brief in DB
        # 5. Create in-app notification (type: COACHING_BRIEF)
        # 6. Queue for email digest
        return brief
```

### LLM Brief Generation Prompt

```
You are a proactive career coach. Generate a short coaching brief (3-5 bullet points)
for this user based on their current career situation.

Context:
- Days since last application: {days_inactive}
- Top new job matches: {top_3_matches}
- Rising skill this week: {top_rising_skill} (up {delta}%)
- Resume score: {resume_score}/100
- LinkedIn profile score: {linkedin_score}/100 (if available)
- Career path alignment: {path_alignment}

Be specific, actionable, and encouraging. Reference actual data.
Format as a JSON array of strings: ["nudge 1", "nudge 2", ...]
```

### Coach API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/coach/brief` | Latest coaching brief |
| GET | `/api/coach/history` | Past briefs |

### Phase 3 Checklist

- [ ] Coach reads Scout and Analyst outputs from state
- [ ] Inactivity detected when no applications in 5+ days
- [ ] LLM brief generated with specific data references
- [ ] Brief stored in DB
- [ ] `COACHING_BRIEF` in-app notification created
- [ ] Bolt AI reads latest brief as additional context

---

## Phase 4 — Writer Agent

### Purpose

Drafts tailored cover letters per job listing. Reads structured resume data + listing details + Scout match rationale. Output is grounded, not template-filled.

### Structure

```
app/writer_agent/
├── __init__.py
├── writer_runner.py     # Main entry point
├── draft_generator.py   # LLM cover letter generation
└── schemas.py           # CoverLetterDraft dataclass
```

### Key Methods

```python
class WriterAgent:
    def draft(user_id: int, internship_id: int) -> CoverLetterDraft:
        # 1. Load structured data
        resume_data = db.get_resume_data(user_id)
        listing = db.get_internship(internship_id)
        match_rationale = db.get_match_rationale(user_id, internship_id)

        # 2. Generate via LLM
        content = draft_generator.generate(resume_data, listing, match_rationale)

        # 3. Store draft with status='draft'
        draft = db.save_cover_letter_draft(user_id, internship_id, content)
        return draft
```

### LLM Cover Letter Prompt

```
Write a professional cover letter for this job application.

Candidate profile:
- Name: {name}
- Skills: {skills}
- Relevant experience: {relevant_experience}
- Relevant projects: {relevant_projects}

Job listing:
- Title: {title}
- Company: {company}
- Required skills: {required_skills}
- Key responsibilities: {description_excerpt}

Match rationale: {match_rationale}

Instructions:
- Open with a strong, specific hook referencing the company
- Mention 2-3 specific experiences or projects relevant to this role
- Reference required skills naturally (not as a list)
- Close with a clear call to action
- 250-300 words, professional tone, no generic phrases
- Do NOT use phrases like "I am writing to express my interest"
```

### Writer API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/drafts/generate` | Trigger Writer for a listing |
| GET | `/api/drafts` | All drafts |
| PATCH | `/api/drafts/:id` | Edit draft |
| PATCH | `/api/drafts/:id/approve` | Approve |
| DELETE | `/api/drafts/:id` | Discard |

### Phase 4 Checklist

- [ ] Writer reads structured resume + listing data (not raw text)
- [ ] LLM generates grounded, non-generic cover letter
- [ ] Draft stored with `status: 'draft'`
- [ ] User can edit, approve, or discard drafts
- [ ] "Generate Cover Letter" button visible on listing + application pages

---

## Phase 5 — Builder Agent

### Purpose

12-step conversational resume creation. Collects structured data, recommends templates, renders preview, optimizes content, exports PDF/DOCX. Post-build triggers Analyzer + Orchestrator automatically.

### Structure

```
app/resume_agent/
├── __init__.py
├── resume_routes.py       # FastAPI router
├── resume_service.py      # Session management, step routing
├── resume_schema.py       # Pydantic models
├── template_engine.py     # Jinja2 rendering + recommendation
├── resume_optimizer.py    # LLM bullet rewriting + ATS scoring
└── export_service.py      # PDF (WeasyPrint) + DOCX (python-docx)

backend/templates/
├── minimal_ats.html
├── developer_modern.html
├── corporate_classic.html
├── student_simple.html
└── technical_professional.html
```

### 12-Step Session Flow

| Step | Field(s) | Agent Question |
|---|---|---|
| 1 | name, email, phone | "Let's build your resume! What's your full name?" |
| 2 | linkedin, portfolio | "What's your LinkedIn profile URL?" |
| 3 | career_interests | "What roles are you targeting?" |
| 4 | skills | "List your technical skills (comma separated)" |
| 5 | education | "Tell me about your education" |
| 6 | experience | "Add your work or internship experience (or skip)" |
| 7 | projects | "Describe a project you're proud of" |
| 8 | certifications | "Add any certifications (or skip)" |
| 9 | achievements | "Any awards, publications, competitions? (or skip)" |
| 10 | — | Show summary, confirm or edit |
| 11 | selected_template | Show AI-recommended templates, user picks one |
| 12 | — | Show preview, accept edits, export |

### Conversational Edit Commands (Step 12)

```python
EDIT_INTENTS = {
    "add.*project":      lambda s: goto_step(s, 7),
    "change.*template":  lambda s: goto_step(s, 11),
    "improve.*":         lambda s: run_optimizer(s),
    "shorten.*":         lambda s: trim_section(s),
    "ats.*friendly":     lambda s: run_ats_pass(s),
    "export.*pdf":       lambda s: export_pdf(s),
    "export.*docx":      lambda s: export_docx(s),
}
```

### ATS Score Breakdown

| Dimension | Max | Criteria |
|---|---|---|
| Structure | 35 | Standard headers, no tables for layout |
| Keyword Density | 40 | Skills match target role listings |
| Completeness | 25 | All key sections present |

### Post-Build Pipeline

```python
def finalize_resume(session_id: str):
    resume_data = get_session_data(session_id)

    # 1. Run Resume Analyzer
    ResumeAnalyzer.analyze_from_data(user_id, resume_data)

    # 2. Save version to resume_versions
    save_version(user_id, resume_data, ats_score)

    # 3. Trigger Orchestrator
    orchestrator.trigger(user_id, trigger="resume_builder_complete")

    # 4. Notify
    notify(user_id, "RESUME_ANALYZED", "Your resume is ready! Recommendations incoming.")
```

### Builder API (15 Endpoints)

| Method | Endpoint |
|---|---|
| POST | `/api/resume-agent/start-session` |
| POST | `/api/resume-agent/answer` |
| GET | `/api/resume-agent/session/:id` |
| GET | `/api/resume-agent/templates` |
| POST | `/api/resume-agent/select-template` |
| GET | `/api/resume-agent/preview/:id` |
| POST | `/api/resume-agent/update-section` |
| POST | `/api/resume-agent/optimize` |
| GET | `/api/resume-agent/ats-score/:id` |
| POST | `/api/resume-agent/finalize` |
| POST | `/api/resume-agent/export-pdf` |
| POST | `/api/resume-agent/export-docx` |
| GET | `/api/resume-agent/versions` |
| GET | `/api/resume-agent/versions/:id` |
| POST | `/api/resume-agent/versions/:id/restore` |

---

## Phase 6 — Interview Agent

### Purpose

Role-specific mock interview. Generates 10 targeted questions from listing + user resume. Evaluates each answer. Produces structured feedback report.

### Structure

```
app/interview_agent/
├── __init__.py
├── interview_routes.py
├── interview_service.py
├── interview_schema.py
├── question_generator.py  # LLM question generation per role
├── answer_evaluator.py    # LLM answer scoring
└── feedback_reporter.py   # Compile final report
```

### Question Generation

```python
def generate_question_set(job_listing, user_profile) -> list[InterviewQuestion]:
    role_category = detect_role_category(job_listing.title, job_listing.required_skills)
    return [
        *generate_technical_questions(role_category, job_listing.required_skills, user_profile.projects),  # 3
        *generate_project_questions(user_profile.projects, job_listing),                                    # 2
        *generate_behavioral_questions(role_category, user_profile.experience_level),                       # 3
        *generate_situational_questions(job_listing.description),                                           # 2
    ]  # Total: 10 questions
```

### Answer Evaluation

```python
# LLM evaluates each answer: score 0-10, verdict, strengths, weaknesses, model_answer, improvement_tip
# technical: correctness + depth + clarity + relevance
# behavioral: STAR structure + specificity + impact + relevance
```

### Readiness Levels

| Score | Level | Message |
|---|---|---|
| ≥ 75 | Ready | "You're well-prepared for this role" |
| 55–74 | Almost Ready | "A few improvements will get you there" |
| < 55 | Needs Prep | "Focus on these 3 areas before applying" |

### Interview API (8 Endpoints)

| Method | Endpoint |
|---|---|
| POST | `/api/interview/start` |
| GET | `/api/interview/session/:id` |
| POST | `/api/interview/answer` |
| POST | `/api/interview/complete` |
| GET | `/api/interview/report/:id` |
| GET | `/api/interview/history` |
| POST | `/api/interview/retry/:id` |
| GET | `/api/interview/questions/:id` |

### Phase 6 Checklist

- [ ] 10 questions generated per session (role-specific)
- [ ] Each answer evaluated individually with score + feedback
- [ ] Report compiled with overall score + readiness level
- [ ] Report stored in `interview_reports`
- [ ] `INTERVIEW_REPORT_READY` notification created
- [ ] Coach Agent reads reports: low score triggers nudge to retry
- [ ] "Prepare for Interview" button on listing and application pages

---

## Phase 7 — LinkedIn Agent

### Purpose

Analyzes gap between resume data (DB) and LinkedIn sections (user-pasted text). Generates actionable copy improvements ready to paste directly into LinkedIn.

**Important**: Does NOT scrape LinkedIn. User pastes their own profile sections. Fully ToS-compliant.

### Structure

```
app/linkedin_agent/
├── __init__.py
├── linkedin_routes.py
├── linkedin_service.py
├── linkedin_schema.py
├── gap_analyzer.py        # Resume vs. LinkedIn diff
├── content_optimizer.py   # LLM rewrites: headline, about, bullets, skills
└── profile_scorer.py      # 0-100 completeness score
```

### Profile Score Breakdown

| Section | Max Points |
|---|---|
| Headline | 20 |
| About | 20 |
| Experience | 20 |
| Skills | 15 |
| Projects | 10 |
| Education | 10 |
| Profile Photo | 5 |
| **Total** | **100** |

### Output: 3 Headline Variants

```
Input: "Computer Science Student at Anna University"
Target roles: ["Backend Developer", "Software Engineer Intern"]

Variant 1 [Keyword-Rich]:   "Backend Developer | Python • FastAPI • PostgreSQL | Seeking SWE Internships 2026"
Variant 2 [Achievement-Led]: "Building AI-Powered Systems | CS @ Anna University | Open to Backend & SWE Roles"
Variant 3 [Role-Focused]:   "Aspiring Software Engineer | Full-Stack + AI/ML Projects | Internship Ready"
```

### LinkedIn API (6 Endpoints)

| Method | Endpoint |
|---|---|
| POST | `/api/linkedin/analyze` |
| GET | `/api/linkedin/report/:id` |
| POST | `/api/linkedin/regenerate` |
| GET | `/api/linkedin/score/:id` |
| GET | `/api/linkedin/history` |
| GET | `/api/linkedin/latest` |

### Phase 7 Checklist

- [ ] User can paste up to 5 LinkedIn sections as text input
- [ ] Gap analysis runs against resume data already in DB
- [ ] 3 headline variants generated
- [ ] About section drafted (or improved if exists)
- [ ] Before/after for every experience bullet
- [ ] Skills to add/remove/reorder identified (including Analyst trends)
- [ ] Profile score (0-100) calculated and shown as gauge
- [ ] Every output section has one-click Copy button in UI
- [ ] Regenerate works inline with user feedback
- [ ] Coach Agent reads LinkedIn score — nudges if score < 50
