from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4


@dataclass(slots=True)
class ArtifactRef:
    artifact_id: str
    kind: str
    path: str | None
    mime_type: str | None


@dataclass(slots=True)
class CaseResult:
    case_id: str
    status: Literal["passed", "failed", "error", "invalid_case"]
    score: float | None
    expected: dict[str, Any]
    actual: dict[str, Any] | None
    latency_ms: int | None
    error: str | None = None


@dataclass(slots=True)
class CaseDelta:
    case_id: str
    current_status: str
    reference_status: str
    score_delta: float | None


@dataclass(slots=True)
class ComparisonResult:
    current_run_id: str
    reference_run_id: str
    summary_delta: dict[str, Any]
    case_deltas: list[CaseDelta]


@dataclass(slots=True)
class RunContext:
    run_id: str
    suite_name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    artifact_dir: Path | None = None


class ArtifactWriter:
    def __init__(self, artifact_dir: Path | None, run_id: str) -> None:
        self._artifact_dir = artifact_dir
        self._run_id = run_id

    def write(
        self,
        name: str,
        content: str | bytes,
        *,
        kind: str = "debug",
        mime_type: str | None = None,
    ) -> ArtifactRef:
        if self._artifact_dir is None:
            artifact_id = f"{self._run_id}:{name}"
            return ArtifactRef(artifact_id=artifact_id, kind=kind, path=None, mime_type=mime_type)

        target_dir = self._artifact_dir / self._run_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / name
        if isinstance(content, bytes):
            target_path.write_bytes(content)
        else:
            target_path.write_text(content, encoding="utf-8")

        artifact_id = f"{self._run_id}:{name}"
        return ArtifactRef(
            artifact_id=artifact_id,
            kind=kind,
            path=str(target_path),
            mime_type=mime_type,
        )


@dataclass(slots=True)
class EvalContext:
    case: EvalCase
    adapter: Any
    run: RunContext
    env: dict[str, Any] = field(default_factory=dict)
    artifact_writer: ArtifactWriter | None = None


@dataclass(slots=True)
class EvalCase:
    id: str
    input: dict[str, Any]
    expected: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    check: Callable[[EvalContext], None] | None = None


@dataclass(slots=True)
class RunResult:
    run_id: str
    suite_name: str
    summary: dict[str, Any]
    metrics: dict[str, Any]
    cases: list[CaseResult]
    artifacts: list[ArtifactRef]
    config: dict[str, Any] = field(default_factory=dict)
    status: str = "completed"

    @property
    def passed(self) -> bool:
        return int(self.summary.get("failed", 0)) == 0 and int(self.summary.get("error", 0)) == 0


class EvalSuite:
    def __init__(
        self,
        *,
        name: str,
        adapter: Any,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.adapter = adapter
        self.description = description
        self.metadata = metadata or {}
        self._cases: list[EvalCase] = []

    @property
    def cases(self) -> tuple[EvalCase, ...]:
        return tuple(self._cases)

    def case(
        self,
        *,
        id: str,
        input: dict[str, Any],
        expected: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> Callable[[Callable[[EvalContext], None]], Callable[[EvalContext], None]]:
        case = EvalCase(
            id=id,
            input=input,
            expected=expected,
            metadata=metadata or {},
        )

        def decorator(check: Callable[[EvalContext], None]) -> Callable[[EvalContext], None]:
            case.check = check
            self._cases.append(case)
            return check

        return decorator

    def new_run_context(self, *, artifact_dir: Path | None = None) -> RunContext:
        return RunContext(
            run_id=str(uuid4()),
            suite_name=self.name,
            metadata=dict(self.metadata),
            artifact_dir=artifact_dir,
        )

    def iter_cases(self) -> list[EvalCase]:
        return list(self._cases)


def _build_summary(results: list[CaseResult]) -> dict[str, int]:
    return {
        "total": len(results),
        "passed": sum(result.status == "passed" for result in results),
        "failed": sum(result.status == "failed" for result in results),
        "error": sum(result.status == "error" for result in results),
        "invalid_case": sum(result.status == "invalid_case" for result in results),
    }


def _build_metrics(results: list[CaseResult]) -> dict[str, float | int | None]:
    scored_results = [result for result in results if result.score is not None]
    latencies = [result.latency_ms for result in results if result.latency_ms is not None]

    accuracy = None
    if scored_results:
        accuracy = sum(float(result.score) for result in scored_results) / len(scored_results)

    average_latency_ms = None
    if latencies:
        average_latency_ms = int(sum(latencies) / len(latencies))

    return {
        "accuracy": accuracy,
        "average_latency_ms": average_latency_ms,
    }


def run_local(
    suite: EvalSuite,
    *,
    output: str = "text",
    artifact_dir: str | Path = ".atalaia",
) -> RunResult:
    artifact_root = Path(artifact_dir)
    run_context = suite.new_run_context(artifact_dir=artifact_root)
    artifact_writer = ArtifactWriter(artifact_root, run_context.run_id)

    case_results: list[CaseResult] = []
    for case in suite.iter_cases():
        if case.check is None:
            case_results.append(
                CaseResult(
                    case_id=case.id,
                    status="invalid_case",
                    score=None,
                    expected=case.expected,
                    actual=None,
                    latency_ms=None,
                    error="case has no check function",
                )
            )
            continue

        context = EvalContext(
            case=case,
            adapter=suite.adapter,
            run=run_context,
            env={},
            artifact_writer=artifact_writer,
        )

        started = perf_counter()
        try:
            case.check(context)
        except AssertionError as exc:
            latency_ms = int((perf_counter() - started) * 1000)
            case_results.append(
                CaseResult(
                    case_id=case.id,
                    status="failed",
                    score=0.0,
                    expected=case.expected,
                    actual=None,
                    latency_ms=latency_ms,
                    error=str(exc) or "assertion failed",
                )
            )
        except Exception as exc:
            latency_ms = int((perf_counter() - started) * 1000)
            case_results.append(
                CaseResult(
                    case_id=case.id,
                    status="error",
                    score=None,
                    expected=case.expected,
                    actual=None,
                    latency_ms=latency_ms,
                    error=f"{exc.__class__.__name__}: {exc}",
                )
            )
        else:
            latency_ms = int((perf_counter() - started) * 1000)
            case_results.append(
                CaseResult(
                    case_id=case.id,
                    status="passed",
                    score=1.0,
                    expected=case.expected,
                    actual=None,
                    latency_ms=latency_ms,
                    error=None,
                )
            )

    summary = _build_summary(case_results)
    metrics = _build_metrics(case_results)
    artifacts = [
        artifact_writer.write(
            "summary.json",
            json.dumps({"summary": summary, "metrics": metrics}, sort_keys=True),
            kind="summary",
            mime_type="application/json",
        )
    ]

    return RunResult(
        run_id=run_context.run_id,
        suite_name=suite.name,
        summary=summary,
        metrics=metrics,
        cases=case_results,
        artifacts=artifacts,
        config=dict(run_context.metadata),
        status="completed",
    )
