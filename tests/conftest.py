from collections.abc import Generator
import socket
import threading
import time
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
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


def _build_test_target_app() -> FastAPI:
    target_app = FastAPI()

    @target_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @target_app.post("/classify")
    def classify(payload: dict[str, Any]) -> dict[str, Any]:
        input_json = payload.get("input", {})
        text = input_json.get("text")

        if not isinstance(text, str):
            return {"oops": True}
        if text.startswith("label:"):
            return {"label": text.removeprefix("label:")}
        if text.startswith("wrong:"):
            return {"label": "wrong-label"}
        return {"oops": True}

    return target_app


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_test_target_server(
    target_app: FastAPI, port: int
) -> tuple[uvicorn.Server, threading.Thread]:
    config = uvicorn.Config(
        target_app, host="127.0.0.1", port=port, log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def _wait_for_server_ready(base_url: str) -> None:
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/health", timeout=0.2)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.05)

    raise RuntimeError("Local target test server did not start")


def _stop_test_target_server(server: uvicorn.Server, thread: threading.Thread) -> None:
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def local_target_base_url() -> Generator[str, None, None]:
    target_app = _build_test_target_app()
    port = _pick_free_port()
    server, thread = _start_test_target_server(target_app, port)
    base_url = f"http://127.0.0.1:{port}"

    try:
        _wait_for_server_ready(base_url)
    except RuntimeError:
        _stop_test_target_server(server, thread)
        raise

    try:
        yield base_url
    finally:
        _stop_test_target_server(server, thread)
