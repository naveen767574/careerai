# Scoring Consistency Fix — Implementation Summary

**Date:** 2026-07-09  
**Status:** ✅ Complete  
**Affected Files:** 5 (3 backend, 2 frontend)

---

## Problem Statement

The system had **three different, disagreeing scoring computations**:

1. **Engine (write path)** — `recommendation_engine.py`: Composite score (0–1) × 100, skills matched at embedding cosine ≥ 0.70
2. **Recommendations read path** — `routes/recommendations.py`: Re-normalized that percentage into a compressed 50–100 band with different label thresholds (88/78/68/58), recomputed matched/missing with exact string intersection
3. **Skill-gap endpoint** — `routes/internships.py`: Exact string intersection, raw 0–100 ratio

**User-visible impact:**
- Same job showed "82%" on card, "40%" on skill-gap view
- Completely unrelated jobs still showed ≥50% due to artificial floor
- Score (semantic) disagreed with matched/missing lists (exact match)
- "Excellent" matches could still list many "missing" skills the engine actually credited

---

## Solution: ONE Canonical System

**Source of truth:** Recommendation engine's composite score (0–100, no compression).

**Unified rules:**
- Match percentage = composite score × 100 (honest 0–100 scale, no artificial floor)
- Label thresholds: 80/70/60/50 (Excellent/Strong/Good/Partial)
- Skill matching: **semantic** (embedding cosine ≥ 0.70) everywhere

---

## Changes Made

### 1. Backend: `routes/recommendations.py`

**Removed:**
- `_normalize_display_score()` function (50–100 compression)
- Dual label logic with 88/78/68/58 thresholds
- Import of `normalize_score` from `embedding_service`

**Changed:**
```python
# BEFORE
def _derive_match_label(display_score: float) -> str:
    """Derive label from normalized display score (50–100 range)."""
    if display_score >= 88:
        return "Excellent Match"
    if display_score >= 78:
        return "Strong Match"
    # ...

# AFTER
def _derive_match_label(raw_percentage: float) -> str:
    """
    Derive label from raw composite score (0–100 range).
    Thresholds chosen for honest 0–100 scale, not compressed.
    """
    if raw_percentage >= 80:
        return "Excellent Match"
    if raw_percentage >= 70:
        return "Strong Match"
    if raw_percentage >= 60:
        return "Good Match"
    if raw_percentage >= 50:
        return "Partial Match"
    return "Low Match"
```

**In `_build_recommendation_item()`:**
```python
# BEFORE
raw_pct = rec.match_percentage or 0.0
display = _normalize_display_score(raw_pct)
label = _derive_match_label(display)

return RecommendationItem(
    # ...
    match_percentage=round(raw_pct, 1),
    display_score=round(display, 1),  # compressed 50-100
    match_label=label,
)

# AFTER
raw_pct = rec.match_percentage or 0.0
label = _derive_match_label(raw_pct)

return RecommendationItem(
    # ...
    match_percentage=round(raw_pct, 1),
    display_score=round(raw_pct, 1),  # now same as match_percentage
    match_label=label,
)
```

**In `explain_recommendation()`:**
```python
# BEFORE
display = _normalize_display_score(rec.match_percentage or 0.0)
return {
    "display_score": round(display, 1),
    "match_label": _derive_match_label(display),
    # ...
}

# AFTER
raw_pct = rec.match_percentage or 0.0
return {
    "display_score": round(raw_pct, 1),
    "match_label": _derive_match_label(raw_pct),
    # ...
}
```

---

### 2. Backend: `schemas/recommendation.py`

**Updated documentation:**
```python
# BEFORE
match_percentage: float       # raw composite score × 100 (stored in DB, used for sorting)
display_score: float          # normalized score for UI display (50–100 range, like LinkedIn)

# AFTER
match_percentage: float       # raw composite score × 100 (0-100 range, used for sorting)
display_score: float          # same as match_percentage — unified scoring, no compression
```

---

### 3. Backend: `routes/internships.py`

**Changed `/internships/{internship_id}/skill-gap` from exact matching to semantic:**

```python
# BEFORE (exact string intersection)
required_set = {s.skill_name.lower() for s in required}
user_set = {s.skill_name.lower() for s in user_skills}
matched = sorted({s.skill_name for s in required if s.skill_name.lower() in user_set})
missing = sorted({s.skill_name for s in required if s.skill_name.lower() not in user_set})

# AFTER (semantic, cosine ≥ 0.70)
from app.services.embedding_service import embed_text, cosine_similarity

SKILL_MATCH_THRESHOLD = 0.70  # must match recommendation_engine.py

user_embeddings = {text: embed_text(text) for text in user_skill_texts}
required_embeddings = {text: embed_text(text) for text in required_skill_texts}

matched = []
missing = []

for req_skill, req_emb in required_embeddings.items():
    best_score = 0.0
    for user_emb in user_embeddings.values():
        if user_emb and any(user_emb):
            score = cosine_similarity(user_emb, req_emb)
            best_score = max(best_score, score)
    
    if best_score >= SKILL_MATCH_THRESHOLD:
        matched.append(req_skill)
    else:
        missing.append(req_skill)
```

**Result:** Skill-gap now uses the SAME matching logic as the recommendation engine.

---

### 4. Frontend: `Internships.tsx`

**Changed score extraction (lines ~182, 207):**
```tsx
// BEFORE
const score = Math.round(rec.display_score ?? rec.match_percentage ?? 0);

// AFTER (display_score now equals match_percentage)
const score = Math.round(rec.match_percentage ?? 0);
```

**Unified badge color thresholds (line ~537):**
```tsx
// BEFORE (search mode used ≥60 for blue)
: (searchScores[String(internship.id)] || 0) >= 60
  ? 'bg-blue-500/20 text-blue-400'

// AFTER (both use ≥70)
: (searchScores[String(internship.id)] || 0) >= 70
  ? 'bg-blue-500/20 text-blue-400'
```

**Fixed "High Match" stat to work in both modes (line ~486):**
```tsx
// BEFORE (always counted internship.match, which was 0 in search mode)
{ label: 'High Match', value: internships.filter(i => i.match >= 70).length.toString() }

// AFTER (checks the right score depending on mode)
{
  label: 'High Match',
  value: internships.filter(i => {
    if (isSearchMode) {
      const score = searchScores[String(i.id)] || 0;
      return score >= 70;
    }
    return i.match >= 70;
  }).length.toString()
}
```

**Clear stale search scores when exiting search (line ~241):**
```tsx
// BEFORE
const handleSearch = () => {
  setShowSuggestions(false);
  setPage(1);
  loadInternships(false, search.trim(), 1);
};

// AFTER
const handleSearch = () => {
  setShowSuggestions(false);
  setPage(1);
  if (!search.trim()) {
    // Exiting search mode - clear search scores
    setSearchScores({});
    setIsSearchMode(false);
  }
  loadInternships(false, search.trim(), 1);
};
```

**Also clear on "Clear All Filters" (line ~390):**
```tsx
// Added setSearchScores({}) and setIsSearchMode(false) to the onClick handler
```

---

## Final Unified Formula

**Match Score (0–100):**
```
composite_score = (
    semantic_similarity    * 0.30 +
    skill_coverage         * 0.25 +
    skill_depth            * 0.20 +
    domain_alignment       * 0.15 +
    seniority_alignment    * 0.10
)
match_percentage = composite_score * 100
```

**Label Thresholds (same everywhere):**
- ≥80: Excellent Match (green)
- ≥70: Strong Match (blue)
- ≥60: Good Match
- ≥50: Partial Match
- <50: Low Match (purple)

**Skill Matching (same everywhere):**
- Embedding cosine similarity ≥ 0.70 = matched
- < 0.70 = missing

---

## Verification Checklist

- [x] `display_score` now equals `match_percentage` (no compression)
- [x] Label thresholds unified: 80/70/60/50 everywhere
- [x] Color thresholds unified: ≥80 green, ≥70 blue everywhere
- [x] Skill-gap uses semantic matching (cosine ≥ 0.70)
- [x] "High Match" stat works in both recommendation and search modes
- [x] Search scores cleared when exiting search mode
- [x] No more artificial 50% floor — honest 0–100 scale

---

## Testing Instructions

1. **Start fresh:** `POST /api/recommendations/refresh` → verify scores in DB match UI exactly
2. **Check consistency:** Pick one internship → compare:
   - Card badge "X% Match"
   - `GET /internships/{id}/skill-gap` → `match_percentage`
   - Should be **identical or very close** (within a few % due to rounding)
3. **Verify matched/missing skills agree with score:** An 80% match should show most required skills as "matched" (not as "missing")
4. **Test edge cases:**
   - Job with 0 required skills → 0% (not 50%)
   - Completely unrelated job → <50% (not ≥50%)
5. **Search mode:** Search "Python developer" → verify badge shows "X% Relevant" with correct colors, "High Match" stat counts search scores

---

*This fix eliminates all three scoring inconsistencies and ensures the same internship displays the same percentage across every view.*

---

# Option B — Persist Semantic matched/missing Skills

**Goal:** ONE semantic matching definition everywhere. Compute matched/missing skills
(cosine ≥ 0.70) ONCE at refresh, persist them, and have every read path return the
stored values. No exact string matching anywhere; no embeddings on read.

## Files changed

1. **`models/recommendation.py`** — added `matched_skills` and `missing_skills`
   (`JSON`, nullable) columns.
2. **`alembic/versions/010_recommendation_skills.py`** — NEW migration, real DDL:
   `ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS matched_skills JSON` (+ missing).
   Idempotent; `down_revision = c3d4e5f6a1b9` (009 head).
3. **`services/recommendation_engine.py`** — `refresh_for_user()` and
   `_persist_recommendations()` now save `scored["matched_skills"]` /
   `scored["missing_skills"]` (the semantic lists the score was built from).
4. **`routes/recommendations.py`**
   - `_build_recommendation_item()` returns `rec.matched_skills` / `rec.missing_skills`
     verbatim (signature simplified — no more `db`/`user_skills`).
   - `/skill-gap` (aggregate) now tallies stored `rec.matched_skills` / `rec.missing_skills`.
   - `/explain/{id}` uses stored values.
   - **Deleted** `_compute_matched_missing()` (exact match) and
     `_get_skill_names_for_internship()`; removed unused `InternshipSkill` import.
5. **`routes/internships.py`**
   - `/explain` and `/{id}/skill-gap` now read stored `Recommendation.matched_skills` /
     `missing_skills` (added `Recommendation` import). Removed the read-time
     `embed_text`/`cosine_similarity` path and the exact-string path.

## REQUIRED before testing (create_all won't add columns to an existing table)

```bash
cd backend && venv\Scripts\activate
alembic upgrade head          # runs migration 010, adds the two columns
```

If Alembic isn't stamped in your DB, the equivalent raw SQL is safe & idempotent:

```sql
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS matched_skills JSON;
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS missing_skills JSON;
```

Then **re-run a refresh** (click Refresh, or `POST /api/recommendations/refresh`) so the
new columns get populated — old rows read as empty `[]` until then.

## Consistency guarantee

`score`, recommendation **skill chips**, `/explain`, and both **skill-gap** endpoints
now all derive from the *same* stored semantic lists. They cannot drift.

---

# Week 1 Step 2 — Skill Gap UI

**Goal:** surface skill gaps clearly, strictly reflecting backend data (no derived
values, no recomputation in the frontend).

## Files changed

1. **`components/SkillGapSection.tsx`** — NEW modular component. Renders:
   - Insight line (from `missing_skills.length` only)
   - ✅ Matched skills as green chips (verbatim)
   - ⚠️ Missing skills as orange chips (verbatim), "Quick wins" badge when 1–3,
     top-3 + "+N more" when >3, "You meet all core requirements 🎯" when 0
   - Placeholder "Start learning →" CTA
2. **`pages/Internships.tsx`**
   - Import + use `SkillGapSection` inside the "Why this matches you?" panel.
   - Carry `matched_skills` / `missing_skills` from the `/recommendations` payload
     onto each card object (`internship.matchedSkills` / `.missingSkills`), so the
     chips share the score's source row.
   - Added a one-line insight under the card header (from `missingSkills.length`).

## Consistency guarantee (frontend)

- Skill **names** are rendered exactly as the API returns them — no filtering,
  re-casing, dedup, or transformation.
- The only value the UI derives is a **count** (`missing_skills.length`) used purely
  for wording ("2 skills away", "Quick wins", "+N more"). It never recomputes the
  score or re-decides matched vs missing.
- `match_percentage` is displayed straight from the API; the frontend never scales it.
- Chips prefer the card's stored arrays (same row as the score); `/explain` payload
  is only a fallback if those are absent.

---

# Week 1 Step 3 — Refresh UX + source logo fix

**Goal:** make refresh feel fast, visible, trustworthy — driven by REAL API state
(no fake progress, no arbitrary timers). Plus fix the "??" source logos.

## Refresh UX (`pages/Internships.tsx`)

- **Removed the fake `setTimeout(..., 4000)`** that gated the old refresh. Progress
  now reflects actual completion: `await recommendationService.refresh()` →
  `await loadInternships()`. The scrape trigger is fire-and-forget and never blocks
  or fails the refresh.
- **State:** added `refreshSuccess` and `refreshError` (alongside `refreshing`).
- **Button:** disabled while running, spinner + "Updating recommendations...",
  hover/tap animations suppressed and `cursor-not-allowed` when disabled.
- **Double-click guard:** `handleRefresh` early-returns if `refreshing` is already true.
- **Skeletons:** while `refreshing`, 4 pulse-animated skeleton cards render and the
  real list fades out (`opacity-0 h-0`) — so stale cards don't linger.
- **Success banner:** green "Recommendations updated" (auto-hides after ~2.5s; this
  timer is cosmetic toast dismissal only, not progress).
- **Error banner:** red message + **Retry** button that re-invokes `handleRefresh`.

Only genuine API state drives progress; the sole `setTimeout` remaining just
auto-dismisses the success toast.

## Source logo fix ("??" → real logos)

Root cause: the DB stores `source` with **inconsistent casing** ("LinkedIn",
"Linkedin", "internshala", "shine", "unstop", ...) but `sourceLogoMap` keys are
lowercase, so `sourceLogoMap["LinkedIn"]` was `undefined` → "??".

- Added `getSourceLogo(source)` — trims + lowercases before the map lookup.
- Used it in the internship mapping (`logo: getSourceLogo(item.source)`).
- Replaced the "??" fallback with a **company-initial avatar**, also revealed via
  `onError` if a PNG 404s. Frontend-only; no backend change.
