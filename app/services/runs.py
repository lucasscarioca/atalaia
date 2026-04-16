from datetime import UTC, datetime
from logging import getLogger
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.enums import ResultStatus, RunStatus, TargetType
from app.db.session import SessionLocal
from app.models.dataset import Dataset, DatasetCase
from app.models.run import Run
from app.models.run_result import RunResult
from app.models.target import Target
from app.schemas.run import CreateRunRequest
from app.services.datasets import get_dataset_or_raise
from app.services.targets import get_target_or_raise
from app.target_client.http import TargetClientError, invoke_target

logger = getLogger(__name__)


class UnsupportedTaskTypeError(Exception):
    pass


class UnsupportedTargetTypeError(Exception):
    pass


class RunNotFoundError(Exception):
    pass


class DatasetHasNoCasesError(Exception):
    def __init__(self, dataset_id: UUID) -> None:
        self.dataset_id = dataset_id
        super().__init__(f"Dataset {dataset_id} has no cases")


def create_run(db: Session, payload: CreateRunRequest) -> Run:
    dataset = get_dataset_or_raise(db, payload.dataset_id)
    target = get_target_or_raise(db, payload.target_id)

    if dataset.task_type.value != "classification":
        raise UnsupportedTaskTypeError(dataset.task_type.value)
    if target.target_type != TargetType.HTTP:
        raise UnsupportedTargetTypeError(target.target_type.value)

    case_count = db.scalar(
        select(func.count()).select_from(DatasetCase).where(DatasetCase.dataset_id == dataset.id)
    )
    if case_count == 0:
        raise DatasetHasNoCasesError(dataset.id)

    run = Run(
        dataset_id=dataset.id,
        target_id=target.id,
        status=RunStatus.QUEUED,
        config_json=payload.config,
        summary_json={},
        metrics_json={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return run


def execute_run_in_background(run_id: UUID) -> None:
    db = SessionLocal()
    logger.info("starting background run execution", extra={"run_id": str(run_id)})
    try:
        run = get_run_or_raise(db, run_id)
        dataset = get_dataset_or_raise(db, run.dataset_id)
        target = get_target_or_raise(db, run.target_id)
        execute_run(db, run, dataset, target)
        logger.info("finished background run execution", extra={"run_id": str(run_id)})
    except Exception as exc:
        logger.exception(
            "background run execution failed", extra={"run_id": str(run_id)}
        )
        _mark_run_failed(db, run_id, exc)
    finally:
        db.close()


def execute_run(db: Session, run: Run, dataset: Dataset, target: Target) -> None:
    logger.info("marking run running", extra={"run_id": str(run.id)})
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    db.commit()

    statement = select(DatasetCase).where(DatasetCase.dataset_id == dataset.id)
    cases = list(db.scalars(statement).all())

    try:
        results = [_execute_classification_case(run, case, target) for case in cases]
        db.add_all(results)
        run.status = RunStatus.COMPLETED
        run.completed_at = datetime.now(UTC)
        run.summary_json = _build_summary(results)
        run.metrics_json = _build_metrics(results)
        db.commit()
        logger.info(
            "completed run execution",
            extra={
                "run_id": str(run.id),
                "total_cases": len(results),
                "passed": run.summary_json["passed"],
                "failed": run.summary_json["failed"],
                "errors": run.summary_json["error"],
            },
        )
    except Exception as exc:
        db.rollback()
        _mark_run_failed(db, run.id, exc)
        raise


def _mark_run_failed(db: Session, run_id: UUID, exc: Exception) -> None:
    run = db.get(Run, run_id)
    if run is None:
        return

    logger.error(
        "marking run failed",
        extra={"run_id": str(run_id), "error_type": exc.__class__.__name__},
    )
    run.status = RunStatus.FAILED
    run.completed_at = datetime.now(UTC)
    run.summary_json = {
        "run_error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        }
    }
    run.metrics_json = {}
    db.commit()


def _execute_classification_case(
    run: Run, case: DatasetCase, target: Target
) -> RunResult:
    expected_label = case.expected_json.get("label")
    input_text = case.input_json.get("text")

    if not isinstance(expected_label, str) or not isinstance(input_text, str):
        return RunResult(
            run_id=run.id,
            dataset_case_id=case.id,
            status=ResultStatus.INVALID_CASE,
            score=None,
            expected_json=case.expected_json,
            actual_json=None,
            latency_ms=None,
            error_type="invalid_case",
            error_message="Case input_json/expected_json does not match classification contract",
        )

    try:
        actual_json, latency_ms = invoke_target(
            target, task_type=case.task_type.value, input_json=case.input_json
        )
    except TargetClientError as exc:
        return _build_error_result(
            run.id,
            case,
            exc.error_type,
            exc.error_message,
            exc.latency_ms,
        )

    actual_label = actual_json.get("label")
    if not isinstance(actual_label, str):
        return RunResult(
            run_id=run.id,
            dataset_case_id=case.id,
            status=ResultStatus.ERROR,
            score=None,
            expected_json=case.expected_json,
            actual_json=actual_json,
            latency_ms=latency_ms,
            error_type="invalid_response",
            error_message="Target response missing string 'label'",
        )

    passed = actual_label == expected_label
    return RunResult(
        run_id=run.id,
        dataset_case_id=case.id,
        status=ResultStatus.PASSED if passed else ResultStatus.FAILED,
        score=1.0 if passed else 0.0,
        expected_json=case.expected_json,
        actual_json=actual_json,
        latency_ms=latency_ms,
        error_type=None,
        error_message=None,
    )


def _build_error_result(
    run_id: UUID,
    case: DatasetCase,
    error_type: str,
    error_message: str,
    latency_ms: int,
) -> RunResult:
    return RunResult(
        run_id=run_id,
        dataset_case_id=case.id,
        status=ResultStatus.ERROR,
        score=None,
        expected_json=case.expected_json,
        actual_json=None,
        latency_ms=latency_ms,
        error_type=error_type,
        error_message=error_message,
    )


def _build_summary(results: list[RunResult]) -> dict[str, int]:
    return {
        "total": len(results),
        "passed": sum(result.status == ResultStatus.PASSED for result in results),
        "failed": sum(result.status == ResultStatus.FAILED for result in results),
        "error": sum(result.status == ResultStatus.ERROR for result in results),
        "invalid_case": sum(
            result.status == ResultStatus.INVALID_CASE for result in results
        ),
    }


def _build_metrics(results: list[RunResult]) -> dict[str, float | int | None]:
    scored_results = [result for result in results if result.score is not None]
    latency_values = [
        result.latency_ms for result in results if result.latency_ms is not None
    ]
    accuracy = None
    if scored_results:
        accuracy = float(
            sum(float(result.score) for result in scored_results) / len(scored_results)
        )

    average_latency_ms = None
    if latency_values:
        average_latency_ms = int(sum(latency_values) / len(latency_values))

    return {
        "accuracy": accuracy,
        "average_latency_ms": average_latency_ms,
    }


def list_runs(
    db: Session,
    *,
    limit: int,
    offset: int,
    status: RunStatus | None = None,
    dataset_id: UUID | None = None,
    target_id: UUID | None = None,
) -> list[Run]:
    statement = select(Run)
    if status is not None:
        statement = statement.where(Run.status == status)
    if dataset_id is not None:
        statement = statement.where(Run.dataset_id == dataset_id)
    if target_id is not None:
        statement = statement.where(Run.target_id == target_id)

    statement = statement.order_by(Run.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def get_run_or_raise(db: Session, run_id: UUID) -> Run:
    run = db.get(Run, run_id)
    if run is None:
        raise RunNotFoundError
    return run


def get_run_summary_or_raise(db: Session, run_id: UUID) -> tuple[Run, list[RunResult]]:
    run = get_run_or_raise(db, run_id)
    statement = (
        select(RunResult)
        .where(RunResult.run_id == run_id)
        .order_by(RunResult.created_at.asc())
    )
    results = list(db.scalars(statement).all())
    return run, results


def list_run_results(
    db: Session,
    run_id: UUID,
    *,
    limit: int,
    offset: int,
    status: ResultStatus | None = None,
) -> list[RunResult]:
    get_run_or_raise(db, run_id)
    statement = select(RunResult).where(RunResult.run_id == run_id)
    if status is not None:
        statement = statement.where(RunResult.status == status)

    statement = statement.order_by(RunResult.created_at.asc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())
