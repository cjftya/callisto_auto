"""Read local, content-free P0/P5 reports; never launches CLI or Android calls.

Each root needs baseline-metadata.json. Each matching scenario/repetition folder
contains one *-result.json and its *-usage.json, plus optional acceptance.json
with human-reviewed task_success, false_pass, recovery_success, evidence_missing,
unsafe_release and action_count. Missing evidence remains null, not success.
"""
import argparse
import json
from pathlib import Path
from statistics import median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from callisto.usage import usage_summary
from callisto.llm_adapter.usage_normalization import COUNTERS


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load(root):
    metadata = read(root / "baseline-metadata.json")
    samples = {}
    for path in sorted(root.rglob("*-result.json")):
        key = path.parent.relative_to(root).as_posix()
        if key in samples:
            raise ValueError("Exactly one result is required per scenario/repetition")
        result = read(path)
        usage_path = path.with_name(path.name.removesuffix("-result.json") + "-usage.json")
        calls = read(usage_path).get("calls", []) if usage_path.exists() else []
        review = read(path.parent / "acceptance.json") if (path.parent / "acceptance.json").exists() else {}
        samples[key] = {"result": result, "calls": calls, "review": review}
    return metadata, samples


def summarize(sample):
    calls, review = sample["calls"], sample["review"]
    total = usage_summary(calls)
    operators = usage_summary([c for c in calls if c.get("agent") == "operator"])
    return {"reported_test_status": sample["result"].get("test_status"),
            "task_success": review.get("task_success"), "false_pass": review.get("false_pass"),
            "recovery_success": review.get("recovery_success"), "evidence_missing": review.get("evidence_missing"),
            "unsafe_release": review.get("unsafe_release"), "action_count": review.get("action_count"),
            "elapsed_seconds": sample["result"].get("elapsed_seconds"),
            "all_agents": total, "operator": operators,
            "summary_calls": sum(c.get("agent") in ("visual_summary", "step_capsule", "summarizer", "operator_summarizer") for c in calls) if calls else None,
            "usage_scopes": sorted({c.get("normalized_usage", {}).get("usage_scope", "unknown") for c in calls}),
            "recall_calls": review.get("recall_calls"), "retry_calls": review.get("retry_calls")}


def compare(a, b):
    ma, sa = a
    mb, sb = b
    contract_fields = ("provider", "cli_version", "model_settings_label", "scenario_revision", "device_configuration_label")
    compatible = all(ma.get(k) is not None and ma.get(k) == mb.get(k) for k in contract_fields)
    rows, reductions = [], []
    for sample in sorted(sa.keys() & sb.keys()):
        before, after = summarize(sa[sample]), summarize(sb[sample])
        same_provider = before["all_agents"]["providers"] == after["all_agents"]["providers"] == [ma.get("provider")]
        old = before["all_agents"]["normalized_uncached_input_tokens"]
        new = after["all_agents"]["normalized_uncached_input_tokens"]
        quality = all(row["task_success"] is True and row["false_pass"] is False
                      and row["evidence_missing"] is False and row["unsafe_release"] is False
                      and row["recovery_success"] is not False for row in (before, after))
        reduction = None
        if compatible and same_provider and quality and old is not None and old > 0 and new is not None:
            reduction = 100 * (1 - new / old)
            reductions.append(reduction)
        rows.append({"sample": sample, "baseline": before, "candidate": after, "uncached_reduction_percent": reduction})
    stop = [r["sample"] for r in rows if any(r["candidate"][k] is True for k in ("false_pass", "evidence_missing", "unsafe_release"))
            or r["candidate"]["recovery_success"] is False
            or (r["baseline"]["task_success"] is True and r["candidate"]["task_success"] is False)]
    return {"matched_samples": len(rows), "metadata_compatible": compatible,
            "unmatched_baseline": sorted(sa.keys() - sb.keys()), "unmatched_candidate": sorted(sb.keys() - sa.keys()),
            "measured_successful_pairs": len(reductions), "median_uncached_reduction_percent": median(reductions) if reductions else None,
            "stop_and_rollback_samples": stop, "auto_enable": False, "samples": rows,
            "assessment": "Review scope/version, identical initial state, recovery and all-agent input/output/cache counters. No automatic acceptance or price estimate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(load(args.baseline), load(args.candidate))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Compared {report['matched_samples']} samples; automatically enabling policies is forbidden")


if __name__ == "__main__":
    main()
