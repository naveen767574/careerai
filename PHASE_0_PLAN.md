# Phase 0 — Instrumentation & Evaluation Harness

**Status:** Proposed · **Owner:** —  · **Prereq for:** every later phase
**Companion doc:** `AI_SYSTEM_PLAN.md` (full roadmap)

---

## 0. Recommendation (decision first, reasoning second)

**Start with Phase 0 (Instrumentation), not Phase 2 (LLM skill extraction).**

This is a firm recommendation, not a hedge. Build the measurement layer *before* you touch the intelligence layer.

### Why Phase 0 first — three arguments

**1. The current system's biggest weakness is not bad AI — it's that we can't *see* anything.**
Right now the system produces a match %, matched/missing skills, and explanations, and **not a single one of these outputs is logged, scored, or compared against ground truth.** We fixed the "1 skill = 56%" bug by reasoning, not by measurement. That worked because the bug was blatant. The next class of problems — "are the extracted skills actually right?", "did explanations get better?", "is ordering good?" — are *subtle* and invisible to eyeballing. You cannot improve what you cannot measure, and you cannot prove you improved it either.

**2. The risk of skipping Phase 0 compounds at every later phase.**
- If we do Phase 2 (LLM skill extraction) first, we'll swap the skill source and *feel* like it's better — but we'll have zero evidence. Extraction can silently regress on whole categories (e.g. it starts hallucinating "leadership" as a skill on every posting) and nobody will notice until a user complains.
- Phase 3 (grounded LLM explanations) is **actively dangerous** without instrumentation. An LLM writing fluent prose about wrong requirements is *convincingly wrong* — the worst possible failure mode. The only defense is a golden set + validation harness that catches "explanation references a skill that isn't in matched_skills." That harness IS Phase 0.
- Phase 5 (learned ranking) is **impossible** without Phase 0. A learned ranker trains on outcome events — apply, interview, offer. If we don't start logging those events *now*, we arrive at Phase 5 with zero training data and have to wait months to collect it. Every week we delay event logging is a week added to Phase 5's start date.

**3. Phase 0 is cheap and non-invasive.** It adds tables and a read-only offline script. It changes no scoring logic, no user-facing behavior, no request latency (events written async/best-effort). It is the lowest-risk phase we will ever do, and it unlocks the value of all the others.

### What goes wrong if we pick Phase 2 first (the wrong choice)

1. **We fly blind.** We ship LLM extraction, it looks nicer in spot-checks, and we declare victory. Two weeks later we discover it dropped "SQL" from 30% of data roles because the prompt over-focused on frameworks. No alarm fired because there was no golden set.
2. **We can't A/B or roll back with evidence.** "Is the new extractor better than the old regex?" becomes a matter of opinion in a meeting instead of a number in a report.
3. **We poison Phase 5's well.** The outcome events we failed to log during Phase 2/3/4 are gone forever. Phase 5 starts from an empty dataset.
4. **Phase 3 becomes reckless.** We layer eloquent explanations on top of unvalidated extraction, and the system becomes *more* persuasive while potentially becoming *less* correct — the exact "fake AI" outcome this whole effort is meant to eliminate.

**Bottom line:** Phase 2 makes the system *smarter*. Phase 0 makes the system *honest and improvable*. We already paid down a huge honesty debt in the last fix; Phase 0 is what keeps it paid down. Do it first.

---

## 1. Goal of the Phase

Stand up the **minimum measurement layer** that lets every future phase be validated with numbers instead of opinions. Concretely, after Phase 0 we can answer:

- "What did the system show this user, and what did they do next?" (event log)
- "For these N known internships, are the extracted skills / match scores / explanations correct?" (golden set + offline eval)
- "Did change X make metric Y go up or down?" (offline eval report, run on demand)

**Non-goal:** changing any scoring, extraction, or explanation logic. Phase 0 observes; it does not intervene.

---

## 2. Scope — exact backend changes

All changes live in the FastAPI backend (`D:\PROJECTS\ai-internship-system\backend`). No frontend changes are required for the minimal version (events can be emitted server-side from existing endpoints). An optional tiny frontend hook is listed under "Later, not now."

### New files

| File | Purpose |
|---|---|
| `app/models/interaction_event.py` | ORM model for the event log (append-only) |
| `app/models/eval_case.py` | ORM model for golden-set cases |
| `app/services/event_logger.py` | Thin, best-effort `log_event(...)` helper — never raises into request path |
| `app/services/offline_eval.py` | Read-only evaluation runner: loads golden set, recomputes, emits metrics |
| `scripts/run_offline_eval.py` | CLI entrypoint: `python -m scripts.run_offline_eval` → prints/writes a report |
| `scripts/seed_golden_set.py` | Loads a curated JSON of hand-labeled cases into `eval_cases` |
| `alembic/versions/011_instrumentation_tables.py` | Migration creating both new tables |
| `data/golden_set.seed.json` | ~20–30 hand-labeled internships (checked into repo) |

### Modified files (event emission call sites — additive only)

| File | Change |
|---|---|
| `app/routes/recommendations.py` | After serving recommendations, emit `recommendations_served` events (best-effort) |
| `app/routes/internships.py` | On `match_insights` / skill-gap view, emit `match_viewed`; on simulation, emit `whatif_simulated` |
| `app/routes/applications.py` (or wherever status changes) | On status change saved→applied→interview→offer/rejected, emit `application_status_changed` |

Emission is a single `event_logger.log_event(...)` call wrapped so a logging failure can **never** break the user request. No business logic moves.

---

## 3. Database schema changes

Two new tables. **Additive only — no existing table is altered.** Migration `011`, `down_revision = "010"`.

### 3.1 `interaction_events` (append-only event log)

| Column | Type | Notes |
|---|---|---|
| `id` | BigInteger PK | high-volume table → bigint |
| `user_id` | FK users.id, nullable, ON DELETE SET NULL | keep events if user deleted (analytics) |
| `event_type` | String(50), not null, indexed | `recommendations_served`, `match_viewed`, `whatif_simulated`, `application_status_changed` |
| `internship_id` | FK internships.id, nullable, ON DELETE SET NULL | context, when applicable |
| `payload` | JSON, nullable | event-specific: e.g. `{shown_ids, match_pcts, rank}` or `{from_status, to_status}` |
| `created_at` | DateTime(tz), server_default now(), indexed | for time-window queries |

Indexes: `(event_type)`, `(user_id)`, `(created_at)`, composite `(event_type, created_at)` for metric rollups.

**Design rules:** append-only (no updates/deletes in app code), nullable FKs with `SET NULL` so it never blocks a delete, `payload` as JSON so we can add event fields without migrations.

### 3.2 `eval_cases` (golden set — hand-labeled ground truth)

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `internship_id` | FK internships.id, nullable, ON DELETE SET NULL | link to a real row when it exists |
| `title` | String(255) | denormalized so the case survives if the internship is deleted |
| `company` | String(255), nullable | |
| `description` | Text | the raw text extraction runs against |
| `expected_skills` | JSON (list[str]) | **human-labeled** correct required skills — the ground truth |
| `expected_role_type` | String(50), nullable | e.g. `data`, `backend`, `frontend` |
| `notes` | Text, nullable | labeler notes / edge-case rationale |
| `created_at` | DateTime(tz), server_default now() | |

`eval_cases` is small (tens of rows), curated, and version-controlled via the seed JSON so it's reproducible.

---

## 4. Step-by-step implementation tasks

1. **Migration 011** — create `interaction_events` + `eval_cases` (`down_revision="010"`). Include the indexes above. Verify with `alembic upgrade head` then `alembic downgrade -1` round-trips cleanly.
2. **ORM models** — `interaction_event.py`, `eval_case.py`. Register them wherever models are imported for metadata (match the existing pattern used by `recommendation.py` etc.).
3. **`event_logger.log_event(db, event_type, *, user_id=None, internship_id=None, payload=None)`** — one insert, wrapped in try/except that logs a warning and swallows on failure. Best-effort by contract. Add a module docstring stating it must never raise into a request.
4. **Wire 4 event types** at existing call sites (additive one-liners):
   - `recommendations_served` — after recommendations are built (payload: list of internship_ids + match_pcts + their order).
   - `match_viewed` — when a user opens skill-gap / match insights for one internship.
   - `whatif_simulated` — when the what-if endpoint runs (payload: skill added, delta shown).
   - `application_status_changed` — on any application status transition (payload: from/to).
5. **Golden set seed** — hand-label ~20–30 internships in `data/golden_set.seed.json` (`{title, company, description, expected_skills, expected_role_type}`). Pull real descriptions from the DB; label skills by hand. Aim for coverage across data/backend/frontend + a couple of thin/garbage postings (the failure cases we care about).
6. **`seed_golden_set.py`** — idempotent loader (upsert by title+company) so re-running doesn't duplicate.
7. **`offline_eval.py`** — read-only. For each eval case: run the *current* skill-extraction path and the *current* scoring, then compute metrics (Section 6). No DB writes to product tables; output a report dict.
8. **`scripts/run_offline_eval.py`** — CLI that runs the eval and writes `data/eval_reports/eval_<timestamp>.json` + prints a one-screen summary. This becomes the "before/after" instrument for every later phase.
9. **Validate** per Section 6 and record a **baseline** report (today's numbers) — the reference every future phase is compared against.

---

## 5. Minimal version (the smallest thing that unblocks Phase 2)

If time is tight, ship exactly this and stop:

- `interaction_events` table + `log_event` helper + **only** the `application_status_changed` and `recommendations_served` events wired. *(These two are the irreplaceable ones — outcome + exposure. Miss them now and Phase 5 has no data.)*
- `eval_cases` table + ~20 hand-labeled cases + `offline_eval.py` computing **only skill-extraction precision/recall** against `expected_skills`.
- `run_offline_eval.py` producing one baseline report.

That's enough to (a) start accumulating outcome data immediately and (b) measure Phase 2's extraction quality on day one. `match_viewed` / `whatif_simulated` events and the richer metrics can follow.

---

## 6. Risks & validation strategy

| Risk | Mitigation |
|---|---|
| Event logging adds latency or breaks a request | `log_event` is best-effort (try/except swallow); emit *after* the response payload is built; keep payloads small. Load-test that a forced logger exception does not surface to the client. |
| Event table grows unbounded | It's append-only and cheap; revisit retention/partitioning only when it's actually large (explicitly **not now** — see Section 7). |
| Golden set too small to be meaningful | 20–30 is enough to catch category-level regressions, which is the goal at this stage. Grow it opportunistically when a real failure is found (add that case to the set). |
| Golden labels are subjective | Store `notes` with rationale; treat the set as versioned via seed JSON so label changes are reviewable in diffs. |
| Offline eval accidentally writes to product tables | `offline_eval.py` opens a read-only session / never commits to product tables; unit-assert no writes. |
| Migration breaks existing DB | `011` is purely additive (new tables, nullable FKs). Validate `upgrade`→`downgrade`→`upgrade` round-trip on a copy before applying. |

**Validation checklist (definition of done):**
- `alembic upgrade head` creates both tables; `downgrade -1` drops them cleanly.
- Hitting the recommendations endpoint inserts a `recommendations_served` row; forcing a logger error still returns a normal 200.
- Changing an application status inserts an `application_status_changed` row with correct from/to.
- `run_offline_eval.py` runs end-to-end and writes a baseline report with per-case + aggregate skill precision/recall.
- **Baseline report committed** as the reference point for Phase 2.

---

## 7. What we should NOT build yet (anti-overengineering guardrails)

- **No analytics dashboard / charts / admin UI.** A JSON report file is enough. Visualization is a distraction now.
- **No streaming/queue/Kafka/event bus.** Direct synchronous best-effort insert into Postgres. We have low volume.
- **No table partitioning, retention jobs, or archival.** Premature at current scale.
- **No experiment framework / feature-flag A/B platform.** Offline eval + manual before/after reports are sufficient until we have live traffic worth splitting.
- **No auto-labeling of the golden set with an LLM.** The whole point is *human* ground truth; auto-labeling defeats it.
- **No frontend event tracking / client SDK yet.** Server-side emission covers every event we need now. Client-side view/hover telemetry is a later refinement.
- **No changes to match %, extraction, or explanations.** Phase 0 is observation-only, by rule.

---

## 8. How Phase 0 connects to the next phase

Phase 0 is the **measuring instrument** every later phase plugs into:

- **→ Phase 2 (LLM skill extraction):** Day one, run `run_offline_eval.py` against the golden set to get extraction precision/recall for the *new* LLM extractor vs. the recorded baseline. Ship only if it beats baseline. The golden set is the acceptance test.
- **→ Phase 3 (grounded explanations):** Reuse the golden set to assert the hard-validation rule — every explanation references only skills in `matched_skills`. The eval harness becomes the guardrail that makes eloquent explanations safe instead of "convincingly wrong."
- **→ Phase 4 (personalization):** `match_viewed` / `whatif_simulated` events describe real engagement, the signal personalization tunes against.
- **→ Phase 5 (learned ranking):** `recommendations_served` (exposure) + `application_status_changed` (outcome) events are the **training data**. Starting them now means Phase 5 has months of labeled data ready instead of starting from zero.

Deterministic match scoring is **untouched** here and stays untouched: models will eventually influence *ordering* (ranking_score) and *explanation text*, never the displayed match % arithmetic. Phase 0 simply records what that deterministic system did so we can prove the smarter layers on top actually help.

---

*Review this plan, then we proceed task-by-task. My suggested first task is Migration 011 + the two irreplaceable events (Section 5's minimal version), so outcome data starts accumulating immediately.*
