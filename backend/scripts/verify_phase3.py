"""
Phase 3 verification — grounding gate, cache behavior, fallback shape.

Runs WITHOUT groq / postgres: the LLM call and the DB session are stubbed, so
this exercises the real validation and control-flow logic in isolation.

Usage (from backend/):  python -m scripts.verify_phase3
"""
import sys
import types

# --- stub `app.config.settings` and the model/DB imports the service needs ---
import app.services.explanation_service as svc
from app.schemas.explanation import ExplanationOutput

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(name)


MATCHED = ["python", "sql"]
MISSING = ["docker"]


def v(raw):
    return svc.validate_explanation(raw, matched_skills=MATCHED, missing_skills=MISSING)


print("\n[1] VALIDATION — grounding gate")

good = """{"matched_skill_explanations":[{"skill":"python","explanation":"drives the data scripts"}],
"missing_skill_advice":[{"skill":"docker","advice":"containerize a project"}],
"summary":"Solid foundation with docker as the gap."}"""
ok, out, reason = v(good)
check("accepts fully grounded output", ok and out is not None, reason)

# invented skill in matched -> must reject
bad1 = """{"matched_skill_explanations":[{"skill":"rust","explanation":"nice"}],
"missing_skill_advice":[],"summary":"x"}"""
ok, out, reason = v(bad1)
check("rejects invented matched skill", not ok, f"reason={reason}")
check("  reason names the offender", "rust" in reason, reason)

# matched skill smuggled into missing advice -> must reject
bad2 = """{"matched_skill_explanations":[],
"missing_skill_advice":[{"skill":"python","advice":"learn it"}],"summary":"x"}"""
ok, out, reason = v(bad2)
check("rejects matched skill placed in missing advice", not ok, f"reason={reason}")

# missing skill smuggled into matched explanations -> must reject
bad3 = """{"matched_skill_explanations":[{"skill":"docker","explanation":"you know it"}],
"missing_skill_advice":[],"summary":"x"}"""
ok, out, reason = v(bad3)
check("rejects missing skill placed in matched explanations", not ok, f"reason={reason}")

# ONE bad item among good ones -> whole response discarded, not partially kept
bad4 = """{"matched_skill_explanations":[{"skill":"python","explanation":"good"},{"skill":"kubernetes","explanation":"invented"}],
"missing_skill_advice":[{"skill":"docker","advice":"try it"}],"summary":"x"}"""
ok, out, reason = v(bad4)
check("one violation discards the ENTIRE response", not ok, f"reason={reason}")

# case / whitespace variance should still ground (validator lowercases)
casey = """{"matched_skill_explanations":[{"skill":" Python ","explanation":"ok"}],
"missing_skill_advice":[{"skill":"Docker","advice":"ok"}],"summary":"x"}"""
ok, out, reason = v(casey)
check("normalizes case+whitespace before grounding", ok, reason)

# malformed inputs
check("rejects empty string", not v("")[0])
check("rejects non-JSON prose", not v("Sure! Here is the explanation.")[0])
check("rejects wrong shape", not v('{"foo": 1}')[0] or True)  # shape -> defaults, then empty summary
ok, out, reason = v('{"foo": 1}')
check("  wrong shape fails on empty summary", not ok, reason)

# markdown fences stripped
fenced = "```json\n" + good + "\n```"
check("strips markdown fences", v(fenced)[0])

print("\n[2] FALLBACK — deterministic shape")
fb = svc.build_fallback(MATCHED, MISSING)
check("fallback is an ExplanationOutput", isinstance(fb, ExplanationOutput))
check(
    "fallback explanation text matches spec",
    fb.matched_skill_explanations[0].explanation == "You have experience in python",
    fb.matched_skill_explanations[0].explanation,
)
check(
    "fallback advice text matches spec",
    fb.missing_skill_advice[0].advice == "Consider learning docker",
    fb.missing_skill_advice[0].advice,
)
check(
    "fallback summary matches spec",
    fb.summary == "This job matches based on your current skills.",
    fb.summary,
)
# the fallback must itself survive the grounding gate
ok, _, reason = v(fb.model_dump_json())
check("fallback is grounded by construction", ok, reason)

print("\n[3] CONTROL FLOW — cache / LLM / fallback")


class FakeJob:
    id = 42
    title = "Data Intern"


class FakeQuery:
    def __init__(self, store): self.store = store
    def filter(self, *a, **k): return self
    def order_by(self, *a, **k): return self
    def first(self): return self.store.get("row")


class FakeDB:
    def __init__(self): self.store = {}; self.added = []; self.commits = 0
    def query(self, *a, **k): return FakeQuery(self.store)
    def add(self, obj): self.added.append(obj); self.store["row"] = obj
    def commit(self): self.commits += 1
    def rollback(self): pass


calls = {"n": 0}


def stub_llm_good(**kwargs):
    calls["n"] += 1
    return good


def stub_llm_hallucinating(**kwargs):
    calls["n"] += 1
    return bad1


def stub_llm_dead(**kwargs):
    calls["n"] += 1
    return None


orig_call = svc._call_llm
orig_get = svc._cache_get
orig_put = svc._cache_put

# 3a: cold cache + good LLM -> source=llm, cache written
cache_store = {}
svc._cache_get = lambda db, u, j, r: cache_store.get((u, j, r))
svc._cache_put = lambda db, u, j, r, o: cache_store.__setitem__((u, j, r), o)
svc._call_llm = stub_llm_good
calls["n"] = 0
out, source = svc.generate_explanation(
    FakeDB(), 1, FakeJob(), MATCHED, MISSING, 72.0, resume_version="v1"
)
check("cold cache -> source=llm", source == "llm", source)
check("  LLM called exactly once", calls["n"] == 1, calls["n"])
check("  result cached", ("1", "42", "v1") in cache_store)

# 3b: warm cache -> NO LLM call
calls["n"] = 0
out, source = svc.generate_explanation(
    FakeDB(), 1, FakeJob(), MATCHED, MISSING, 72.0, resume_version="v1"
)
check("warm cache -> source=cache", source == "cache", source)
check("  LLM NOT called on cache hit", calls["n"] == 0, calls["n"])

# 3c: hallucinating LLM -> fallback, nothing cached
cache_store.clear()
svc._call_llm = stub_llm_hallucinating
calls["n"] = 0
out, source = svc.generate_explanation(
    FakeDB(), 2, FakeJob(), MATCHED, MISSING, 72.0, resume_version="v1"
)
check("hallucinating LLM -> source=fallback", source == "fallback", source)
check("  bad output NOT cached", len(cache_store) == 0, cache_store)
check(
    "  fallback content served",
    out.matched_skill_explanations[0].explanation == "You have experience in python",
)

# 3d: dead LLM (no key / timeout) -> fallback
svc._call_llm = stub_llm_dead
out, source = svc.generate_explanation(
    FakeDB(), 3, FakeJob(), MATCHED, MISSING, 72.0, resume_version="v1"
)
check("dead LLM -> source=fallback", source == "fallback", source)

# 3e: no skills at all -> no LLM call
calls["n"] = 0
svc._call_llm = stub_llm_good
out, source = svc.generate_explanation(
    FakeDB(), 4, FakeJob(), [], [], 0.0, resume_version="v1"
)
check("empty skill sets -> fallback, no LLM call", source == "fallback" and calls["n"] == 0)

# 3f: different resume_version busts the cache
cache_store.clear()
svc.generate_explanation(FakeDB(), 5, FakeJob(), MATCHED, MISSING, 72.0, resume_version="v1")
calls["n"] = 0
out, source = svc.generate_explanation(
    FakeDB(), 5, FakeJob(), MATCHED, MISSING, 72.0, resume_version="v2"
)
check("new resume_version busts cache", source == "llm" and calls["n"] == 1, source)

svc._call_llm, svc._cache_get, svc._cache_put = orig_call, orig_get, orig_put

print("\n" + ("=" * 50))
if FAILURES:
    print(f"FAILED ({len(FAILURES)}): {FAILURES}")
    sys.exit(1)
print("ALL CHECKS PASSED")
