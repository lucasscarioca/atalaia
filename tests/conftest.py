from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.main import app
from app.models.dataset import Dataset, DatasetCase
from app.models.run import Run
from app.models.run_result import RunResult
from app.models.target import Target


@pytest.fixture
def clean_db_tables() -> Generator[None, None, None]:
    db = SessionLocal()
    try:
        db.execute(delete(RunResult))
        db.execute(delete(Run))
        db.execute(delete(DatasetCase))
        db.execute(delete(Target))
        db.execute(delete(Dataset))
        db.commit()
        yield
    finally:
        db.execute(delete(RunResult))
        db.execute(delete(Run))
        db.execute(delete(DatasetCase))
        db.execute(delete(Target))
        db.execute(delete(Dataset))
        db.commit()
        db.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
