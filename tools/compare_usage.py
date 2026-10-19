"""Compare actual local run reports. One result per matching relative sample directory.

Example: traces/off/settings/01/<session>-result.json and
traces/balanced/settings/01/<session>-result.json. Missing usage stays unknown.
"""
import argparse
import json
from pathlib import Path
from statistics import median


def load_runs(root):
    runs = {}
    for path in sorted(root.rglob("*-result.json")):
        key = path.parent.relative_to(root).as_posix()
        if key in runs:
            raise ValueError("Each scenario/repetition directory must contain exactly one result")
        runs[key] = json.loads(path.read_text(encoding="utf-8"))
    return runs


def measured(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def compare(baseline, candidate):
    rows = []
    for sample in sorted(baseline.keys() & candidate.keys()):
        before, after = baseline[sample], candidate[sample]
        a, b = before.get("usage", {}), after.get("usage", {})
        old, new = a.get("input_tokens"), b.get("input_tokens")
        reduction = 100 * (1 - new / old) if measured(old) and old > 0 and measured(new) else None
        rows.append({"sample": sample, "baseline_input_tokens": old, "candidate_input_tokens": new,
                     "input_reduction_percent": reduction,
                     "baseline_passed": before.get("test_status") == "passed",
                     "candidate_passed": after.get("test_status") == "passed",
                     "baseline_elapsed_seconds": before.get("elapsed_seconds"),
                     "candidate_elapsed_seconds": after.get("elapsed_seconds"),
                     "baseline_images": a.get("image_attachments"), "candidate_images": b.get("image_attachments"),
                     "baseline_failed_calls": a.get("failed_calls"), "candidate_failed_calls": b.get("failed_calls")})
    reductions = [r["input_reduction_percent"] for r in rows if r["input_reduction_percent"] is not None]
    return {"matched_samples": len(rows), "unmatched_baseline": sorted(baseline.keys()-candidate.keys()),
            "unmatched_candidate": sorted(candidate.keys()-baseline.keys()),
            "measured_token_pairs": len(reductions), "unknown_token_pairs": len(rows)-len(reductions),
            "median_input_reduction_percent": median(reductions) if reductions else None,
            "baseline_pass_rate": sum(r["baseline_passed"] for r in rows)/len(rows) if rows else None,
            "candidate_pass_rate": sum(r["candidate_passed"] for r in rows)/len(rows) if rows else None,
            "regressions": [r["sample"] for r in rows if r["baseline_passed"] and not r["candidate_passed"]],
            "samples": rows, "assessment": "Manual accuracy/failure review and identical starting device state are required."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(compare(load_runs(args.baseline),load_runs(args.candidate)), indent=2))
    except (OSError, ValueError):
        parser.exit(1, "Invalid comparison input; inspect the report files and sample directory structure.\n")


if __name__ == "__main__":
    main()
