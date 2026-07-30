# Phase 2 — LLM-Based Skill Extraction

**Status:** Proposed · **Prereq:** Phase 0 (done) · **Graded by:** `offline_eval.py`
**Companion docs:** `AI_SYSTEM_PLAN.md`, `PHASE_0_PLAN.md`

Baseline to beat (keyword extractor, from Phase 0):

| metric | baseline | meaning | Phase 2 target |
|---|---|---|---|
| precision | **0.97** | extracted skills that are real | **≥ 0.92** (must not drop much) |
| recall | **0.64** | real skills we actually found | **≥ 0.85** (the whole point) |
| f1 | **0.75** | — | **≥ 0.88** |
| thin_clean_rate | (report) | invented nothing on empty postings | **= 1.00** (no regressions) |

The one-line mandate: **raise recall to ≥0.85 without letting precision fall below 0.92, and never hallucinate a skill on a garbage posting.**

---

## 0. Critical context discovered in the codebase (read this first)

There are **two** skill extractors today, and the baseline measures the weaker one:

1. **`app/services/skill_extractor.py`** — spaCy + a **32-word** keyword set. This is what `offline_eval.py` and `resume_analyzer.py` call. **It is the 0.97 / 0.64 / 0.75 baseline.** Its tiny dictionary is the direct cause of recall 0.64.
2. **`app/scraper/utils/extractor.py`** — a **200+ skill taxonomy** (`SKILLS_DICTIONARY`), an **alias map** (`SKILL_ALIASES`, ~60 entries: `js→javascript`, `k8s→kubernetes`, …), and an **existing Groq LLM fallback** (`llama-3.1-8b-instant`, temp 0.0) that only fires when the rule layer finds < 3 skills.

**Consequence for the plan:** Phase 2 does **not** build an LLM extractor from nothing. It:
- **reuses the existing assets** — the 200-skill taxonomy and alias map from the scraper extractor become the shared normalization vocabulary,
- builds **one** LLM-first extractor that produces the required `{skills, role_type}` JSON,
- makes **that** the measured path (swap it in behind `offline_eval.py`),
- keeps the keyword extractor as the **deterministic fallback**,
- reuses `role_stack.detect_role()` (already exists) for the fallback role and as a cross-check.

This avoids a third parallel extractor and keeps one source of truth for the skill vocabulary.

---

## 1. Goal

Replace the keyword `SkillExtractor` as the **primary** extraction path with an LLM-first pipeline that emits validated, normalized, structured JSON — measurably lifting recall while holding precision — with a deterministic fallback so the system never depends on the LLM being up.

Non-goals (explicitly out of scope for Phase 2): changing match %, changing scoring, async queues, re-embedding, or re-extracting the whole DB in this phase (that's a controlled backfill, listed at the end).

---

## 2. Architecture

```
        extract_skills(text, title)                ← same call signature as today
                  │
                  ▼
   ┌─────────────────────────────┐
   │ 1. LLM extraction (Groq)     │  llama-3.1-8b-instant, temp 0.0, JSON prompt
   │    → {skills[], role_type}   │
   └─────────────────────────────┘
                  │ raw model JSON
                  ▼
   ┌─────────────────────────────┐
   │ 2. VALIDATION LAYER          │  parse → shape-check → per-skill checks
   │    reject if malformed       │
   └─────────────────────────────┘
                  │ valid? ──── no ──────────────┐
                  │ yes                           │
                  ▼                               ▼
   ┌─────────────────────────────┐   ┌────────────────────────────┐
   │ 3. NORMALIZE + GROUND        │   │ 4. FALLBACK                │
   │    alias map → canonical     │   │    keyword SkillExtractor  │
   │    drop skills not in        │   │    (current 0.97/0.64 path)│
   │    taxonomy (anti-halluc.)   │   │    role via detect_role()  │
   └─────────────────────────────┘   └────────────────────────────┘
                  │                               │
                  └──────────────┬────────────────┘
                                 ▼
                   {"skills": [...], "role_type": "..."}   ← always this shape
```

**Precision-protecting principle (the anti-hallucination core):** the LLM is used for **recall** (it proposes skills the keyword layer misses), but every proposed skill is **grounded against the known taxonomy** before it's accepted. A skill the model invents that isn't in the 200-skill vocabulary (after alias normalization) is dropped. This is how we get the LLM's recall *without* inheriting its hallucinations — the model can only "unlock" skills we already recognize, it cannot fabricate new ones. Grounding is a **hard gate**, not a suggestion to the model.

> Design note: grounding to a fixed taxonomy caps recall at "skills in the taxonomy." That's the right trade for Phase 2 (precision is sacred, the taxonomy already has 200+). Growing the taxonomy is a cheap, safe, additive follow-up (Section 9) driven by the eval's `missing` lists — not an LLM free-for-all.

---

## 3. Code-level implementation plan

### 3.1 New shared vocabulary module — `app/services/skill_taxonomy.py`
Lift `SKILLS_DICTIONARY` + `SKILL_ALIASES` out of `app/scraper/utils/extractor.py` into one importable module so both the scraper and the new extractor share **one** vocabulary. Provide:

```python
CANONICAL_SKILLS: set[str]          # the 200+ taxonomy (single source of truth)
SKILL_ALIASES: dict[str, str]       # alias → canonical
def normalize_skill(raw: str) -> str | None:
    """lowercase/strip → alias-map → return canonical if in taxonomy else None."""
```
`normalize_skill` returning `None` for unknown terms IS the grounding gate. Keep `scraper/utils/extractor.py` importing from here (no behavior change to the scraper).

### 3.2 New extractor — `app/services/llm_skill_extractor.py`
The primary path. Public surface mirrors the old one so callers don't change:

```python
class LLMSkillExtractor:
    @staticmethod
    def extract(text: str, title: str = "") -> dict:
        """→ {"skills": list[str], "role_type": str}. Never raises."""
    @staticmethod
    def extract_skills(text: str, title: str = "") -> list[str]:
        """Back-comp shim: returns just the skills list."""
```
Internally: build prompt → call Groq (temp 0.0, `response_format` json if available) → `validate_llm_output()` → normalize+ground each skill → derive/------cross-check `role_type` → on ANY failure, `return _keyword_fallback(text, title)`.

`role_type` output is constrained to `{"data","backend","frontend","general"}` (the four the task requires). Map the model's answer through a tiny dict; if it returns anything else, fall back to `role_stack.detect_role()` collapsed into those four buckets.

### 3.3 Validation layer — `app/services/skill_extraction_validation.py`
Pure, testable, no I/O (Section 5 details). Returns `(ok: bool, cleaned: dict, reason: str)`.

### 3.4 Swap the measured path — `offline_eval.py`
Change the one import + call so the harness measures the new extractor, keeping the label mechanism:
```python
from app.services.llm_skill_extractor import LLMSkillExtractor
...
predicted = {normalize... for s in LLMSkillExtractor.extract_skills(c.description, c.title)}
```
Run with `--name llm_v1`. The keyword baseline report stays on disk for comparison.

### 3.5 Callers — **no breaking changes**
- `resume_analyzer.py` uses `SkillExtractor.extract_skills(...)`/`normalize_skills(...)`. Keep the old class intact (it's the fallback). Decide per-caller whether to upgrade resume extraction to the LLM path **in a later phase** — Phase 2 only swaps the *job-posting* extraction path and the eval. Do not touch resume extraction now (out of scope, avoids scope creep).
- Downstream (`recommendation_engine`, `career_match_service`, match %) consumes a **list of skill strings**. The output contract is unchanged (`skills` is still `list[str]`, lowercased, canonical), so **nothing downstream changes**. `role_type` is additive.

### 3.6 Config — `app/config.py`
Add small, safe knobs (defaults keep current behavior; no new required env):
```python
LLM_SKILL_EXTRACTION_ENABLED: bool = True   # kill-switch → forces keyword fallback
LLM_EXTRACTION_MODEL: str = "llama-3.1-8b-instant"
LLM_EXTRACTION_TIMEOUT_S: float = 8.0
```
If `GROQ_API_KEY` is empty or `LLM_SKILL_EXTRACTION_ENABLED` is false → always fallback. This makes the LLM strictly additive and instantly reversible.

---

## 4. Example prompt (exact)

System + user, temperature **0.0**, `max_tokens` ~300. Request strict JSON. The prompt is recall-oriented but the taxonomy grounding (post-processing) is what protects precision — so we can safely ask the model to be generous.

```
SYSTEM:
You extract technical skills from internship/job postings. You return ONLY a
single JSON object, no prose, no markdown fences. You never invent skills that
are not clearly implied by the text.

USER:
From the job posting below, extract the technical skills it requires and classify
the role.

Return EXACTLY this JSON shape and nothing else:
{"skills": ["<skill>", ...], "role_type": "data" | "backend" | "frontend" | "general"}

Rules:
- Include concrete technical skills only: programming languages, frameworks,
  libraries, databases, cloud/devops tools, data/ML tools, and platforms.
- Include a skill even if mentioned once or implied by a well-known framework
  (e.g. "Django REST" implies "python" and "rest api"). Prefer RECALL.
- Do NOT include soft skills, company names, job perks, degrees, or generic
  words ("motivated", "fast-paced", "team player").
- Normalize to canonical lowercase names: "JS"→"javascript", "Node"→"nodejs",
  "postgres"→"postgresql", "k8s"→"kubernetes", "sk-learn"→"scikit-learn".
- role_type: "data" (data science/ML/analytics), "backend" (server/APIs/infra),
  "frontend" (UI/web/mobile clients), else "general".
- If the posting has no real technical content, return {"skills": [], "role_type": "general"}.

Job title: {title}
Job posting:
{description_truncated_to_~1500_chars}
```

Notes:
- **Empty-input guard:** if `not (title or text)`, skip the call and return `{"skills": [], "role_type": "general"}` — protects `thin_clean_rate` and saves quota.
- Truncate description (~1500 chars) — internship JDs are short; caps tokens/latency/cost.
- Temp 0.0 → effectively deterministic output (satisfies "deterministic system" intent; the *match %* is untouched regardless).

---

## 5. Validation logic (reject bad outputs)

`validate_and_ground(raw_text) -> (ok, {"skills","role_type"}, reason)`:

1. **Parse.** Strip markdown fences (reuse the existing `"```"` split trick), locate the outermost `{...}`, `json.loads`. Fail → reject.
2. **Shape.** Must be a dict with `skills` (list) and `role_type` (str). Fail → reject.
3. **Per-skill grounding (the precision gate):** for each item in `skills`:
   - must be a non-empty `str`, length ≤ 40, no newlines/URLs,
   - `canonical = normalize_skill(item)`; **drop if `None`** (not in taxonomy after alias mapping).
   Dedupe, sort. This is where hallucinations die.
4. **role_type:** lowercased; if not in `{data,backend,frontend,general}` → set from `detect_role()` bucket (don't reject the whole extraction for a bad label).
5. **Sanity caps:** if the model returns > 25 skills → keep the 25 that ground (defends against a runaway dump). Empty `skills` is **valid** (thin postings legitimately have none) — do NOT treat empty as failure.
6. **Accept** → return grounded dict. Any hard failure in 1–3 → `ok=False` → caller uses keyword fallback.

Because validation only ever *removes* ungrounded skills, the LLM path's precision is bounded below by "how clean the taxonomy is," not "how honest the model is."

---

## 6. Fallback mechanism

Fallback triggers (any of): `GROQ_API_KEY` empty, kill-switch off, network/timeout/exception, unparseable JSON, or validation `ok=False`. Fallback = the **current keyword `SkillExtractor.extract_skills`** (0.97/0.64 path) for skills + `detect_role()` for `role_type`. So:

- Worst case, we are exactly as good as today (never worse).
- The LLM is pure upside on recall; it can never drag the system below the baseline you already validated.
- Log which path served each extraction (`layer="llm"|"fallback"`, reason) so the eval/analytics can see fallback rate.

---

## 7. How we evaluate improvement (using the Phase 0 harness)

The measurement is already built — Phase 2 just points it at the new extractor:

1. **Baseline is on disk** from Phase 0 (`data/eval_reports/eval_keyword_v1_*.json`): P 0.97 / R 0.64 / F1 0.75.
2. Point `offline_eval.py` at `LLMSkillExtractor` (Section 3.4). Run:
   ```
   python -m scripts.run_offline_eval --name llm_v1
   ```
3. **Compare** the two report JSONs (aggregate + per-case `missing`/`spurious`). The runner already prints the 5 weakest cases — watch which `missing` skills the LLM recovers and whether any new `spurious` ones appear.
4. **Iterate on the prompt/taxonomy, not the scoring.** If recall is short, the per-case `missing` lists tell you exactly which real skills to add to the taxonomy (Section 9). If precision dips, `spurious` lists tell you which model outputs to tighten.

### Success criteria (ship gate)
Ship `llm_v1` as the primary path **only if all hold** on the golden set:

- **recall ≥ 0.85** (primary objective; ≥ +0.21 over baseline)
- **precision ≥ 0.92** (hard floor; at most ~0.05 below baseline)
- **f1 ≥ 0.88**
- **thin_clean_rate = 1.00** (zero hallucinations on the 3 garbage/thin cases)
- **fallback rate < 20%** on the golden set (the LLM should actually be serving, not silently falling back)

If precision < 0.92 → the taxonomy/validation is letting junk through: tighten grounding, don't relax the floor. If recall < 0.85 but precision is fine → grow the taxonomy from the `missing` lists and re-run. **Do not ship on vibes — ship on the report.**

---

## 8. What we should NOT build yet (anti-overengineering)

- **No async queue / batch worker.** Extraction stays synchronous, one posting at a time (matches current code; the scraper already `sleep`s for rate limits).
- **No fine-tuning / embeddings-based extraction / NER training.** Prompt + taxonomy grounding is enough to clear the targets.
- **No multi-model ensembles or self-consistency voting.** One call, temp 0.0.
- **No resume-extraction changes.** Phase 2 is job-posting extraction + eval only.
- **No taxonomy auto-expansion by the LLM.** Taxonomy grows by human review of eval `missing` lists (safe, precision-preserving).
- **No full-DB re-extraction as part of shipping the code.** The backfill is a separate, controlled, rate-limited job (Section 9) run after the eval gate passes.
- **No change to match %, weights, thresholds, or `ranking_score`.** Untouched.

---

## 9. Rollout & connection to the next phase

**Ship order:**
1. Land `skill_taxonomy.py` (refactor, no behavior change) + `llm_skill_extractor.py` + validation, behind `LLM_SKILL_EXTRACTION_ENABLED`.
2. Run the eval gate (Section 7). Only proceed if criteria pass.
3. Point the **scraper's** new-job path at `LLMSkillExtractor` so *new* postings get LLM extraction going forward.
4. **Controlled backfill** (separate script, rate-limited like the existing 2.5s sleep): re-extract existing internships' `required_skills` + `InternshipSkill` rows, then trigger a recommendations refresh so scores reflect the richer skills. Grow the taxonomy from the eval `missing` lists first, re-run the gate, then backfill.

**Connection to Phase 3 (grounded explanations):** Phase 3 generates prose explaining *why* a user matches. That is only safe on top of accurate requirements — eloquent explanations over garbage skill lists are "convincingly wrong," the worst state. Phase 2 supplies the clean, grounded requirements Phase 3's explanations stand on, and the same golden-set harness enforces Phase 3's hard rule (explanations reference only real matched skills). Phase 2 is the foundation that makes Phase 3 not dangerous.

**Connection to Phase 5 (learned ranking):** cleaner skills → cleaner matched/missing → a stronger `ranking_score` feature set, while the displayed match % stays the same deterministic coverage arithmetic. Models influence ordering and text, never the number the user sees.

---

*Review this plan. Suggested first task: extract `skill_taxonomy.py` (pure refactor, zero behavior change) so both extractors share one vocabulary — then build the LLM extractor + validation against it, then run the eval gate.*
