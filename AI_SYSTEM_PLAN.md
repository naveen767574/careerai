# AI Job Matching System – Architecture & Implementation Plan

**Status:** Draft v1 · **Scope:** Evolution of CareerAI from a heuristic matching engine into a production-grade AI recommendation system
**Audience:** Engineers working on `backend/app/services/` and the recommendation surfaces

---

## 1. System Assessment (Honest Inventory)

### 1.1 What is REAL AI today

| Component | Where | Verdict |
|---|---|---|
| Sentence embeddings + pgvector cosine retrieval | `refresh_for_user` → `_fetch_top_internships_for_refresh` (top-50 ANN pre-select) | **Real ML.** Correct production primitive for candidate retrieval. Keep and build on. |
| Semantic skill matching (cosine ≥ 0.70 to decide matched vs missing) | `MatchScoringAgent._semantic_skill_match` | **Real ML**, though shallow — pairwise skill-to-skill similarity, no skill relationships. |
| `EmbeddingCache` | `recommendation_engine.py` | Not AI, but correct engineering that makes the ML layer viable at request time. |

That is the complete list. Roughly 1.5 of the 4 places AI belongs (extraction, retrieval, ranking, generation).

### 1.2 What is heuristic / template ("fake AI")

| Component | Where | Problem |
|---|---|---|
| Role detection | `role_stack.py::_ROLE_RULES` | Keyword lists. Misclassifies anything phrased unusually → falls back to `GENERAL_ROLE`. |
| Stack detection | `role_stack.py::_STACK_SIGNATURES` | Token-boundary keyword scoring. Fine as a fallback, not as authority. |
| Skill importance (core/important/optional) | `SkillClassifier` + `SKILL_WEIGHTS` | Hand-authored frozensets. "Importance" is a guess baked into code, not learned. |
| "Why you match" / recommendations | `career_match_service.py::_ROLE_CONTEXT`, `_ROLE_SKILL_HELP`, `_SKILL_SPECIFIC_HELP` | Mad-Lib templates: `{skill} + {role clause}`. Two users comparing cards will see identical "mentor advice." Honest (never hallucinates a skill) but not intelligent. |
| Match score | `match_percentage = matched_weight / total_weight × 100` | Honest arithmetic, deliberately so — but a ratio, not a prediction of interview probability. |
| Composite ranking weights | `DEFAULT_WEIGHTS` (0.30/0.25/0.20/0.15/0.10) | Invented numbers. Currently demoted to a ranking tiebreaker (correct), but still unvalidated. |

### 1.3 Biggest architectural weaknesses (ranked)

1. **Job data quality — the root defect.** Scraped listings (Internshala/Unstop/Shine) carry thin, noisy skill lists (sometimes literally `["python"]`). Every downstream surface — coverage %, skill gap, "All matched 🎯" — is only as good as this input. The 100%-match epidemic is *honest scoring of garbage input*.
2. **No learning loop.** `BehaviorProfileBuilder` collects signals, but nothing ever trains on outcomes (apply/reject/interview). The system is frozen at the quality of its hand-written rules.
3. **No evaluation harness.** No offline metrics (precision@k, NDCG), no golden set, no A/B capability. Every change to matching is a vibe, not a measurement.
4. **No skill taxonomy.** Skills are normalized strings. "PyTorch" doesn't imply "Python"; "ReactJS"/"React.js"/"React" are luck-of-the-scrape. Matching is pairwise-embedding, not structured.
5. **Scale ceiling.** `get_recommendations` scores every active internship per call; refresh is on-demand per user. Fine at 10³ jobs, dead at 10⁵.
6. **No cold-start strategy.** New user without resume/behavior → degenerate results.

### 1.4 What was recently fixed (do not regress)

- Single canonical score: `match_percentage` = weighted skill coverage, stored once, read verbatim everywhere.
- What-if simulator delta is *exactly* the change in the displayed score (`w_s/total_w × 100`).
- Explanations constrained to real matched skills only (no hallucinated skills).
- Role-gated stack detection (a Data role can never show "Go Backend").
- Canonical thresholds (`HIGH_MATCH_THRESHOLD=75`, `ALL_MATCHED_THRESHOLD=90`, etc.).

This consistency discipline is the **precondition** for everything below. The scoring core is now a clean, swappable module.

---

## 2. Target Architecture (Production-Grade)

### 2.1 Data flow

```
┌────────────── OFFLINE INGESTION PIPELINE (batch) ──────────────┐
│ Scrapers (Internshala/Unstop/Shine)                            │
│   → Dedup (repost detection, URL/content hashing)              │
│   → Quality filter (ghost jobs, spam, expired)                 │
│   → LLM STRUCTURED EXTRACTION from full description:           │
│       required_skills[] / preferred_skills[] / seniority /     │
│       role_type / domain / stipend / location                  │
│   → Skill normalization against canonical taxonomy             │
│   → Job embedding → pgvector                                   │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────── ONLINE SERVING (per request) ────────────────────┐
│ 1. RETRIEVAL: user preference vector → pgvector ANN → ~200     │
│ 2. RANKING: learned model (LTR) over features:                 │
│      skill coverage · semantic sim · taxonomy proximity ·      │
│      behavior affinity · recency · location/stipend fit        │
│ 3. SCORE DISPLAY: keep honest coverage % as the shown number;  │
│    ranking model orders the list (never displayed as fake %)   │
│ 4. EXPLANATION: LLM, grounded + validated, cached per          │
│    (user, job, resume_version)                                 │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────── FEEDBACK LOOP (continuous) ──────────────────────┐
│ view / save / dismiss / apply / interview → labeled events     │
│   → periodic LTR retraining → offline eval gate → deploy       │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 Where AI/LLMs SHOULD be used

- **Extraction (LLM, offline):** turning messy job descriptions into structured requirements. Highest-leverage LLM use in the whole system; runs once per job, so cost is bounded.
- **Retrieval (embeddings):** already present; extend the user side into a real preference vector.
- **Ranking (learned model):** gradient-boosted trees or logistic regression over features first — *not* a neural net on day one.
- **Explanation (LLM, online, cached):** grounded generation constrained to real matched skills, schema-validated (extend the existing `ExplanationOutput` pydantic pattern).
- **Resume parsing:** structured extraction of skills/experience from resumes.

### 2.3 Where NOT to use AI

- **The displayed match %.** Keep it deterministic, explainable arithmetic (weighted coverage). Users must be able to verify it against the skill chips. An opaque model-generated % destroys trust.
- **Thresholds, gates, dedup, filtering, alerts.** Plain code.
- **Anything in the hot path that a lookup can do** (skill normalization after the taxonomy exists).
- **Validation of LLM output.** Deterministic pydantic schemas + "skill must be in matched_skills" checks — never "LLM checks the LLM" as the only guard.

### 2.4 Personalization strategy

- **Level 0 (today):** skill-set intersection. Keep as baseline/fallback.
- **Level 1:** whole-resume embedding + explicit preferences (location, stipend, role interest) as retrieval filters.
- **Level 2:** behavior-adjusted preference vector — saves/applies pull the user vector toward those job embeddings (simple online update, no training infra needed).
- **Level 3:** learned per-user features inside the ranking model (interaction history, dwell, dismissals).
- **Cold start:** content-only (resume embedding + coverage) + popularity prior among similar-cohort users.

### 2.5 Learning loop (minimum viable)

1. Event table: `(user_id, internship_id, event_type[view|save|dismiss|apply|interview], surfaced_rank, score_at_time, ts)`.
2. Nightly job builds training pairs (shown-and-ignored vs shown-and-acted).
3. Retrain ranker weekly; evaluate on held-out weeks (NDCG@10, precision@5, apply-rate).
4. Deploy behind a flag; compare online apply-rate vs baseline before full rollout.

---

## 3. Phase-by-Phase Roadmap

### Phase 0 — Instrumentation & Ground Truth *(do first, ~small)*
- **Goal:** Be able to measure anything before changing anything.
- **Changes:** Event logging table (views/saves/dismisses/applies with rank + score at time of display); a hand-labeled golden set of ~100 (user, job, relevance) judgments; offline metric script (precision@k / NDCG@k against golden set).
- **Why:** Without this, Phases 2–5 cannot prove they helped. Cheapest phase, unlocks all others.
- **Impact:** Invisible to users; foundational.

### Phase 1 — Truth & Trust Cleanup *(mostly done)*
- **Goal:** Nothing on screen is misleading.
- **Changes:** Honest coverage score, consistency across surfaces, no hallucinated skills, role-gated labels — **largely shipped.** Remaining: label the score in the UI ("skill coverage — based on your resume vs listed requirements"), demote/remove "AI-matched" copy until Phase 3 earns it.
- **Why:** Trust, and a clean swappable scoring seam.
- **Impact:** Fewer absurd 100% cards; honest low scores (expect user-visible score *drops* — this is correct, communicate it).

### Phase 2 — Job Data Quality: LLM Skill Extraction *(highest impact)*
- **Goal:** Score against what the job actually requires, not the scraped skill field.
- **Changes:**
  - Offline pipeline step: LLM extracts `required[]`, `preferred[]`, `seniority`, `role_type` from the full description into a new `job_requirements` table (schema-validated, batch, cached — one call per job ever).
  - Canonical skill taxonomy table + normalization (alias map first: React.js→react; graph relations later).
  - Dedup + ghost-job filtering in the scraper.
  - `_get_required_skills` reads extracted requirements; keyword `role_stack.py` becomes the fallback when LLM extraction is missing.
- **Why:** Root cause of the 100%-match epidemic and thin skill gaps. Every downstream surface improves simultaneously without touching them.
- **Impact:** Largest single quality jump in the product. Measured via Phase 0 golden set.

### Phase 3 — Real AI Explanations (Grounded LLM)
- **Goal:** Replace template dictionaries with generated, personalized, *validated* explanations.
- **Changes:** LLM receives (matched skills, missing skills w/ weights, job requirements, role, resume highlights) → structured output (per-skill reasons, gap advice) → pydantic validation + hard check that every referenced skill ∈ matched_skills → cached per (user, job, resume_version). Delete `_ROLE_CONTEXT` / `_ROLE_SKILL_HELP` / `_SKILL_SPECIFIC_HELP`; keep templates only as the LLM-failure fallback.
- **Why:** This is the user-facing "is this actually AI?" moment. Only safe *after* Phase 2 (garbage requirements → confidently wrong explanations).
- **Impact:** Differentiated UX; per-user, per-job prose that survives side-by-side comparison.

### Phase 4 — Personalization & Behavior Loop
- **Goal:** The system adapts to each user without full ML infra.
- **Changes:** Whole-resume preference embedding; behavior-adjusted user vector (saves/applies nudge retrieval); explicit preference filters (location/stipend/role) respected in retrieval; dismissals suppress similar jobs; cold-start fallback path.
- **Why:** Converts logged behavior (Phase 0) into visible adaptation cheaply — no training pipeline yet.
- **Impact:** Recommendations visibly change as the user interacts; higher save/apply rates.

### Phase 5 — Learned Ranking (LTR)
- **Goal:** Replace hand-tuned ordering with a model trained on real outcomes.
- **Changes:** Feature vector per (user, job) from existing signals; gradient-boosted ranker trained on Phase 0/4 event labels; weekly retrain; offline eval gate; A/B flag. **Displayed % stays deterministic coverage** — the model only orders the list.
- **Why:** This is the step that makes the system *learn*. Requires months of Phase 0 data — hence last.
- **Impact:** Compounding quality improvements; the moat competitors can't copy from screenshots.

**Dependencies:** 0 → 2 → 3, and 0 → 4 → 5. (2 and 4 can partially overlap; 3 strictly follows 2; 5 strictly follows 0+4.)

---

## 4. Prioritization

- **Single highest-impact improvement: Phase 2 (LLM job-skill extraction + taxonomy).** It fixes the root data defect that makes even honest scoring look fake, and every surface inherits the fix for free.
- **Do FIRST: Phase 0 (instrumentation).** It's a week of work, and without it Phase 2's impact can't be proven, Phase 5 can never exist, and every debate becomes opinion vs opinion.
- **Sequencing mistake to avoid:** jumping to LLM explanations (Phase 3) first because it *looks* most "AI." Generating eloquent prose about garbage requirements makes the product *more* convincingly wrong — the most dangerous possible state.

## 5. Risks & Anti-Patterns

1. **LLM-washing:** sprinkling LLM calls onto bad data to look intelligent. Fix data first.
2. **Model-generated match %:** never let an opaque model produce the displayed number; users must be able to audit it against visible chips. (Ranking ≠ scoring.)
3. **Two competing scores:** the pre-fix bug. One stored score, read verbatim, everywhere. Any new model outputs *ordering*, not a second percentage.
4. **Ungrounded generation:** every LLM explanation must pass "references only real matched skills" validation. No exceptions, even when it reads well.
5. **Online LLM calls in the hot path:** extraction is offline-batch; explanations are cached. A recommendation list render should trigger zero LLM calls.
6. **Neural nets before baselines:** GBDT/logistic ranker over good features beats a premature deep model with no data. Earn complexity with evidence.
7. **Skipping evaluation:** every phase ships with a metric it moved. If you can't name the metric, the phase isn't done.
8. **Deleting the heuristics entirely:** keyword role detection and templates become *fallbacks* for LLM failure/cost modes — degrade gracefully, don't 500.
9. **Ignoring score drops after honesty fixes:** users will see lower numbers. Frame it in the UI ("based on listed requirements") rather than quietly re-inflating.

## 6. Implementation Notes

- The scoring seam is clean: `MatchScoringAgent.score_match` returns `skill_coverage` (displayed) and `composite_score` (ranking tiebreak). Phase 5 replaces the tiebreak, never the displayed number.
- `ExplanationOutput` (pydantic validation of LLM output) is the pattern to extend in Phase 3.
- Canonical constants live in `recommendation_engine.py` (`HIGH_MATCH_THRESHOLD` etc.) — import, never fork.
- New tables needed: `job_requirements` (Phase 2), `skill_taxonomy`/`skill_aliases` (Phase 2), `interaction_events` (Phase 0), `explanation_cache` (Phase 3).
- Both write paths (`get_recommendations`, `refresh_for_user`) must always be modified together — they have drifted before.
