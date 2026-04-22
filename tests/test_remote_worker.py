from __future__ import annotations

from dataclasses import dataclass, field

from oak_eval import RunResult
from oak_eval.bundle import package_suite_bundle
from oak_eval.worker import OakEvalWorker


@dataclass
class FakeClient:
    completed: list[RunResult] = field(default_factory=list)

    def list_runs(self, *, status: str | None = None, project_slug: str | None = None) -> list[str]:
        assert status == "queued"
        assert project_slug is None
        return ["run-1"]

    def get_run(self, run_id: str) -> RunResult:
        return RunResult(
            run_id=run_id,
            suite_name="sample",
            summary={"total": 1, "passed": 0, "failed": 0, "error": 0, "invalid_case": 1},
            metrics={"accuracy": None, "average_latency_ms": None},
            cases=[],
            artifacts=[],
            config={"suite_spec": "evals.sample:suite", "bundle": package_suite_bundle("evals.sample:suite")},
            status="queued",
        )

    def start_run(self, run_id: str) -> RunResult:
        return self.get_run(run_id)

    def complete_run(self, run_id: str, result: RunResult) -> RunResult:
        self.completed.append(result)
        return result


def test_worker_processes_queued_runs() -> None:
    worker = OakEvalWorker(client=FakeClient())

    processed = worker.process_once()

    assert processed == 1
    assert len(worker.client.completed) == 1
    assert worker.client.completed[0].status == "completed"
    assert worker.client.completed[0].cases[0].status == "passed"
