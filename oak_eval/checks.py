from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .comparison import compare_runs
from .core import RunResult


@dataclass(slots=True)
class ThresholdReport:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def evaluate_run_thresholds(
    result: RunResult,
    *,
    min_pass_rate: float | None = None,
    min_accuracy: float | None = None,
) -> ThresholdReport:
    reasons: list[str] = []
    details: dict[str, Any] = {}

    total = int(result.summary.get("total", 0))
    passed = int(result.summary.get("passed", 0))
    pass_rate = 1.0 if total == 0 else passed / total
    details["pass_rate"] = pass_rate
    if min_pass_rate is not None:
        details["min_pass_rate"] = min_pass_rate
        if pass_rate < min_pass_rate:
            reasons.append(f"pass rate {pass_rate:.3f} is below minimum {min_pass_rate:.3f}")

    accuracy = result.metrics.get("accuracy")
    details["accuracy"] = accuracy
    if min_accuracy is not None:
        details["min_accuracy"] = min_accuracy
        if accuracy is None:
            reasons.append("accuracy metric is unavailable")
        elif float(accuracy) < min_accuracy:
            reasons.append(f"accuracy {float(accuracy):.3f} is below minimum {min_accuracy:.3f}")

    return ThresholdReport(passed=not reasons, reasons=reasons, details=details)


def evaluate_comparison_thresholds(
    current: RunResult,
    reference: RunResult,
    *,
    max_failed_delta: int | None = None,
    max_error_delta: int | None = None,
    min_accuracy_delta: float | None = None,
) -> ThresholdReport:
    comparison = compare_runs(current=current, reference=reference)
    reasons: list[str] = []
    details: dict[str, Any] = {
        "summary_delta": comparison.summary_delta,
        "case_deltas": [
            {
                "case_id": delta.case_id,
                "current_status": delta.current_status,
                "reference_status": delta.reference_status,
                "score_delta": delta.score_delta,
            }
            for delta in comparison.case_deltas
        ],
    }

    failed_delta = int(comparison.summary_delta.get("failed", 0))
    error_delta = int(comparison.summary_delta.get("error", 0))
    details["failed_delta"] = failed_delta
    details["error_delta"] = error_delta

    if max_failed_delta is not None:
        details["max_failed_delta"] = max_failed_delta
        if failed_delta > max_failed_delta:
            reasons.append(f"failed cases increased by {failed_delta}, above maximum {max_failed_delta}")

    if max_error_delta is not None:
        details["max_error_delta"] = max_error_delta
        if error_delta > max_error_delta:
            reasons.append(f"errors increased by {error_delta}, above maximum {max_error_delta}")

    current_accuracy = current.metrics.get("accuracy")
    reference_accuracy = reference.metrics.get("accuracy")
    if current_accuracy is not None and reference_accuracy is not None:
        accuracy_delta = float(current_accuracy) - float(reference_accuracy)
        details["accuracy_delta"] = accuracy_delta
        if min_accuracy_delta is not None:
            details["min_accuracy_delta"] = min_accuracy_delta
            if accuracy_delta < min_accuracy_delta:
                reasons.append(
                    f"accuracy delta {accuracy_delta:.3f} is below minimum {min_accuracy_delta:.3f}"
                )
    elif min_accuracy_delta is not None:
        details["min_accuracy_delta"] = min_accuracy_delta
        reasons.append("accuracy delta is unavailable")

    return ThresholdReport(passed=not reasons, reasons=reasons, details=details)
