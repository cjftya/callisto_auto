"""One settlement rule for both the persisted report and the process exit code."""

def settle_report(report: dict) -> None:
    result = report.get("result")
    content = result.get("content") if isinstance(result, dict) else None
    summary = content.get("test_summary") if isinstance(content, dict) else None
    counts = ("passed", "failed", "inconclusive", "unchecked")
    valid = isinstance(summary, dict) and bool(summary) and all(
        type(summary.get(key, 0)) is int and summary.get(key, 0) >= 0 for key in counts
    )
    if not valid:
        verdict = "not_reported"
    elif summary.get("failed", 0):
        verdict = "failed"
    elif summary.get("inconclusive", 0) or summary.get("unchecked", 0):
        verdict = "incomplete"
    elif summary.get("passed", 0):
        verdict = "passed"
    else:
        verdict = "not_reported"
    status = report.get("status")
    exit_code = (130 if status == "cancelled" else
                 1 if status != "completed" or verdict == "failed" else
                 0 if verdict == "passed" else 2)
    report.update(test_status=verdict, exit_code=exit_code)
