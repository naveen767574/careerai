"""
scripts/run_offline_eval.py

CLI entrypoint for the Phase 0 offline evaluation.

Runs the current skill extractor over the golden set, prints a one-screen
summary, and writes a timestamped JSON report to data/eval_reports/. That report
is the BASELINE every later phase is compared against — commit it.

Usage (from backend/):
    python -m scripts.run_offline_eval
    python -m scripts.run_offline_eval --name keyword_v1
    python -m scripts.run_offline_eval --no-write        # print only

Prereq: golden set seeded (python -m scripts.seed_golden_set).
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from app.services.offline_eval import run_eval, report_to_dict

REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "eval_reports"


def _print_summary(payload: dict) -> None:
    agg = payload["aggregate"]
    print()
    print("=" * 60)
    print(f"  OFFLINE EVAL — extractor: {payload['extractor']}")
    print("=" * 60)
    print(f"  cases evaluated : {payload['n_cases']}  ({agg['n_thin']} thin/garbage)")
    print("  -- skill extraction vs golden ground truth --")
    print(f"  macro precision : {agg['macro_precision']:.3f}   (are extracted skills real?)")
    print(f"  macro recall    : {agg['macro_recall']:.3f}   (did we find the real ones?)")
    print(f"  macro f1        : {agg['macro_f1']:.3f}")
    print(f"  thin clean rate : {agg['thin_clean_rate']:.3f}   (1.0 = invented nothing on empty postings)")
    print("=" * 60)

    # Show the worst 5 real cases by F1 so regressions are eyeball-able.
    real = [c for c in payload["cases"] if not c["is_thin"]]
    worst = sorted(real, key=lambda c: c["f1"])[:5]
    if worst:
        print("  Weakest cases (lowest F1):")
        for c in worst:
            print(f"    [{c['f1']:.2f}] {c['title']} — missing={c['missing']} spurious={c['spurious']}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 offline evaluation")
    parser.add_argument("--name", default="llm_v1", help="label for the extractor under test")
    parser.add_argument("--no-write", action="store_true", help="print summary without writing a report file")
    args = parser.parse_args()

    report = run_eval(extractor_name=args.name)
    payload = report_to_dict(report)

    _print_summary(payload)

    if args.no_write:
        return

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = REPORTS_DIR / f"eval_{args.name}_{stamp}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"  report written: {out}")
    print()


if __name__ == "__main__":
    main()
