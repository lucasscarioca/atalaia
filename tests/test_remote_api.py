from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from oak_eval import load_suite, run_local
from oak_eval.bundle import package_suite_bundle


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


def test_remote_api_requires_token() -> None:
    response = client.post("/projects", json={"slug": "demo", "name": "Demo"})

    assert response.status_code == 401


def test_remote_api_can_register_project_suite_and_run(tmp_path) -> None:
    token = _create_token()
    headers = {"Authorization": f"Bearer {token}"}

    project_response = client.post(
        "/projects",
        headers=headers,
        json={"slug": "demo", "name": "Demo Project"},
    )
    assert project_response.status_code == 200
    assert project_response.json()["slug"] == "demo"

    suite_response = client.post(
        "/projects/demo/suites",
        headers=headers,
        json={
            "slug": "sample",
            "name": "Sample Suite",
            "cases": [
                {"case_key": "case-1", "input": {"text": "hi"}, "expected": {"text": "hi"}},
            ],
        },
    )
    assert suite_response.status_code == 200
    assert suite_response.json()["suite"]["slug"] == "sample"

    run_response = client.post(
        "/runs",
        headers=headers,
        json={
            "suite_spec": "evals.sample:suite",
            "project_slug": "demo",
            "suite": {
                "name": "Sample Suite",
                "description": "demo",
                "metadata": {},
                "cases": [
                    {"id": "case-1", "input": {"text": "hi"}, "expected": {"text": "hi"}},
                ],
            },
            "bundle": package_suite_bundle("evals.sample:suite"),
        },
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["run_id"]

    queue_response = client.get("/runs", headers=headers, params={"status_filter": "queued"})
    assert queue_response.status_code == 200
    assert queue_response.json()[0]["run_id"] == run_id

    start_response = client.post(f"/runs/{run_id}/start", headers=headers)
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    duplicate_start = client.post(f"/runs/{run_id}/start", headers=headers)
    assert duplicate_start.status_code == 409

    result = run_local(load_suite("evals.sample:suite"), artifact_dir=tmp_path)
    complete_response = client.post(
        f"/runs/{run_id}/complete",
        headers=headers,
        json={
            "status": "completed",
            "summary": result.summary,
            "metrics": result.metrics,
            "cases": [
                {
                    "case_id": case.case_id,
                    "status": case.status,
                    "score": case.score,
                    "expected": case.expected,
                    "actual": case.actual,
                    "latency_ms": case.latency_ms,
                    "error": case.error,
                }
                for case in result.cases
            ],
            "artifacts": [
                {
                    "artifact_key": artifact.artifact_id.split(":", 1)[-1],
                    "kind": artifact.kind,
                    "path": artifact.path,
                    "mime_type": artifact.mime_type,
                    "payload": {"summary": result.summary, "metrics": result.metrics},
                }
                for artifact in result.artifacts
            ],
        },
    )
    assert complete_response.status_code == 200

    run_detail = client.get(f"/runs/{run_id}", headers=headers)
    assert run_detail.status_code == 200
    data = run_detail.json()
    assert data["status"] == "completed"
    assert data["config"]["bundle"]["format"] == "zip"
    assert data["summary"]["total"] == 1
    assert data["summary"]["passed"] == 1
    assert len(data["cases"]) == 1
    assert len(data["artifacts"]) == 2
    assert any(
        artifact["payload"] and artifact["payload"]["module_name"] == "evals.sample"
        for artifact in data["artifacts"]
    )

    duplicate_complete = client.post(
        f"/runs/{run_id}/complete",
        headers=headers,
        json={
            "status": "completed",
            "summary": result.summary,
            "metrics": result.metrics,
            "cases": [],
            "artifacts": [],
        },
    )
    assert duplicate_complete.status_code == 409
