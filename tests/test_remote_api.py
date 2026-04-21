from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


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


def test_remote_api_can_register_project_suite_and_run() -> None:
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
            "project_slug": "demo",
            "suite": {
                "name": "Sample Suite",
                "description": "demo",
                "metadata": {},
                "cases": [
                    {"id": "case-1", "input": {"text": "hi"}, "expected": {"text": "hi"}},
                ],
            },
        },
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["run_id"]

    run_detail = client.get(f"/runs/{run_id}", headers=headers)
    assert run_detail.status_code == 200
    data = run_detail.json()
    assert data["status"] == "queued"
    assert data["summary"]["total"] == 1
    assert data["summary"]["invalid_case"] == 1
    assert len(data["cases"]) == 1
    assert len(data["artifacts"]) == 1
