from __future__ import annotations

from .core import CaseDelta, ComparisonResult, RunResult


def compare_runs(*, current: RunResult, reference: RunResult) -> ComparisonResult:
    current_cases = {case.case_id: case for case in current.cases}
    reference_cases = {case.case_id: case for case in reference.cases}
    case_ids = sorted(set(current_cases) | set(reference_cases))

    case_deltas: list[CaseDelta] = []
    for case_id in case_ids:
        current_case = current_cases.get(case_id)
        reference_case = reference_cases.get(case_id)
        if current_case is None:
            case_deltas.append(
                CaseDelta(
                    case_id=case_id,
                    current_status="missing",
                    reference_status=reference_case.status if reference_case else "missing",
                    score_delta=None,
                )
            )
            continue
        if reference_case is None:
            case_deltas.append(
                CaseDelta(
                    case_id=case_id,
                    current_status=current_case.status,
                    reference_status="missing",
                    score_delta=None,
                )
            )
            continue

        current_score = current_case.score or 0.0
        reference_score = reference_case.score or 0.0
        case_deltas.append(
            CaseDelta(
                case_id=case_id,
                current_status=current_case.status,
                reference_status=reference_case.status,
                score_delta=current_score - reference_score,
            )
        )

    summary_delta = {
        key: current.summary.get(key, 0) - reference.summary.get(key, 0)
        for key in sorted(set(current.summary) | set(reference.summary))
        if isinstance(current.summary.get(key, 0), (int, float))
        and isinstance(reference.summary.get(key, 0), (int, float))
    }
    return ComparisonResult(
        current_run_id=current.run_id,
        reference_run_id=reference.run_id,
        summary_delta=summary_delta,
        case_deltas=case_deltas,
    )
