from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from oak_eval import RunResult, load_suite
from oak_eval.bundle import package_suite_bundle
from oak_eval.client import OakEvalClient
from oak_eval.worker import OakEvalWorker


engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def _create_token() -> str:
    response = client.post(
        "/auth/tokens",
        headers={"X-Oak-Eval-Admin-Token": "dev-bootstrap"},
        json={"name": "ci"},
    )
    assert response.status_code == 200
    return response.json()["token"]


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


def test_remote_run_waits_for_worker_completion(tmp_path) -> None:
    token = _create_token()
    shared_client = TestClient(app)
    api_client = OakEvalClient(base_url="", token=token, client=shared_client)
    worker = OakEvalWorker(client=api_client)

    suite = load_suite("evals.sample:suite")
    handle = api_client.run(suite, suite_spec="evals.sample:suite", project_slug="demo", wait=False)

    assert handle.run_id
    assert api_client.get_run(handle.run_id).status == "queued"

    processed = worker.process_once()
    assert processed == 1

    result = handle.wait(timeout=5)
    assert result.status == "completed"
    assert result.passed is True
    assert result.summary["passed"] == 1


def test_worker_reports_missing_bundle_as_failure() -> None:
    @dataclass
    class MissingBundleClient:
        completed: list[RunResult] = field(default_factory=list)

        def list_runs(self, *, status: str | None = None, project_slug: str | None = None) -> list[str]:
            assert status == "queued"
            return ["run-2"]

        def get_run(self, run_id: str) -> RunResult:
            return RunResult(
                run_id=run_id,
                suite_name="sample",
                summary={"total": 1, "passed": 0, "failed": 0, "error": 0, "invalid_case": 1},
                metrics={"accuracy": None, "average_latency_ms": None},
                cases=[],
                artifacts=[],
                config={"suite_spec": "evals.sample:suite"},
                status="queued",
            )

        def start_run(self, run_id: str) -> RunResult:
            return self.get_run(run_id)

        def get_run_artifact(self, run_id: str, artifact_key: str) -> dict[str, object]:
            assert artifact_key == "suite.bundle"
            return {"payload": None}

        def complete_run(self, run_id: str, result: RunResult) -> RunResult:
            self.completed.append(result)
            return result

    worker = OakEvalWorker(client=MissingBundleClient())

    processed = worker.process_once()

    assert processed == 1
    assert worker.client.completed[0].status == "failed"
    assert "missing a usable suite bundle" in worker.client.completed[0].cases[0].error
