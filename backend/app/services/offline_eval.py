"""
app/services/offline_eval.py

Offline evaluation harness (Phase 0 — Instrumentation).

READ-ONLY. Runs the CURRENT skill-extraction path over the human-labeled golden
set (`eval_cases`) and reports how well extraction recovers the ground-truth
`expected_skills`. This is the yardstick every later phase is graded against:
Phase 2's LLM extractor must beat the baseline this produces today.

What it measures (per case + aggregate):
  • precision = |predicted ∩ expected| / |predicted|   (are extracted skills real?)
  • recall    = |predicted ∩ expected| / |expected|     (did we find the real ones?)
  • f1        = harmonic mean

Thin/garbage cases (expected_skills == []) are scored separately as a
"false-positive rate on empty postings" — this is exactly the signal behind the
false "100% match" problem, so it gets its own headline number.

It writes NOTHING to product tables. It only reads `eval_cases`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Optional

from app.database import SessionLocal
from app.models.eval_case import EvalCase
from app.services.llm_skill_extractor import LLMSkillExtractor


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _prf(predicted: set[str], expected: set[str]) -> tuple[float, float, float]:
    """Precision, recall, F1 for one case. Empty-set edge cases handled explicitly."""
    if not expected and not predicted:
        # Correct: nothing required, nothing extracted.
        return 1.0, 1.0, 1.0
    if not expected:
        # Thin/garbage posting but the extractor invented skills → precision 0.
        return 0.0, 1.0, 0.0
    if not predicted:
        # Real requirements exist but nothing was extracted → recall 0.
        return 1.0, 0.0, 0.0

    tp = len(predicted & expected)
    precision = tp / len(predicted)
    recall = tp / len(expected)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


@dataclass
class CaseResult:
    case_id: int
    title: str
    company: Optional[str]
    role_type: Optional[str]
    expected: list[str]
    predicted: list[str]
    matched: list[str]
    missing: list[str]        # expected but not predicted
    spurious: list[str]       # predicted but not expected
    precision: float
    recall: float
    f1: float
    is_thin: bool             # expected_skills was empty


@dataclass
class EvalReport:
    n_cases: int
    # Aggregate over cases WITH real requirements (expected non-empty).
    macro_precision: float
    macro_recall: float
    macro_f1: float
    # Thin/garbage cases (expected empty): fraction where extractor stayed correctly empty.
    n_thin: int
    thin_clean_rate: float    # 1.0 = extractor invented nothing on empty postings
    extractor: str            # which extraction path produced these numbers
    cases: list[CaseResult] = field(default_factory=list)


def run_eval(extractor_name: str = "llm_v1") -> EvalReport:
    """
    Evaluate the current PRIMARY extractor (LLMSkillExtractor) against the golden
    set. Read-only.

    `extractor_name` is recorded in the report so before/after comparisons across
    phases are labeled. Pass the extractor's version label (e.g. "llm_v1"); the
    keyword baseline was recorded earlier as "keyword_v1".
    """
    session = SessionLocal()
    try:
        cases = session.query(EvalCase).order_by(EvalCase.id).all()

        results: list[CaseResult] = []
        for c in cases:
            expected = {_normalize(s) for s in (c.expected_skills or []) if s}
            predicted = {
                _normalize(s)
                for s in LLMSkillExtractor.extract_skills(c.description or "", c.title or "")
            }

            precision, recall, f1 = _prf(predicted, expected)
            results.append(
                CaseResult(
                    case_id=c.id,
                    title=c.title,
                    company=c.company,
                    role_type=c.expected_role_type,
                    expected=sorted(expected),
                    predicted=sorted(predicted),
                    matched=sorted(predicted & expected),
                    missing=sorted(expected - predicted),
                    spurious=sorted(predicted - expected),
                    precision=round(precision, 3),
                    recall=round(recall, 3),
                    f1=round(f1, 3),
                    is_thin=not expected,
                )
            )

        real = [r for r in results if not r.is_thin]
        thin = [r for r in results if r.is_thin]

        macro_p = round(mean(r.precision for r in real), 3) if real else 0.0
        macro_r = round(mean(r.recall for r in real), 3) if real else 0.0
        macro_f1 = round(mean(r.f1 for r in real), 3) if real else 0.0

        # On thin postings, "clean" == extractor predicted nothing (precision 1.0 here).
        thin_clean = sum(1 for r in thin if not r.predicted)
        thin_clean_rate = round(thin_clean / len(thin), 3) if thin else 1.0

        return EvalReport(
            n_cases=len(results),
            macro_precision=macro_p,
            macro_recall=macro_r,
            macro_f1=macro_f1,
            n_thin=len(thin),
            thin_clean_rate=thin_clean_rate,
            extractor=extractor_name,
            cases=results,
        )
    finally:
        session.close()


def report_to_dict(report: EvalReport) -> dict:
    """Serialize an EvalReport to a plain dict for JSON output."""
    return {
        "extractor": report.extractor,
        "n_cases": report.n_cases,
        "aggregate": {
            "macro_precision": report.macro_precision,
            "macro_recall": report.macro_recall,
            "macro_f1": report.macro_f1,
            "n_thin": report.n_thin,
            "thin_clean_rate": report.thin_clean_rate,
        },
        "cases": [
            {
                "case_id": r.case_id,
                "title": r.title,
                "company": r.company,
                "role_type": r.role_type,
                "precision": r.precision,
                "recall": r.recall,
                "f1": r.f1,
                "is_thin": r.is_thin,
                "expected": r.expected,
                "predicted": r.predicted,
                "matched": r.matched,
                "missing": r.missing,
                "spurious": r.spurious,
            }
            for r in report.cases
        ],
    }
