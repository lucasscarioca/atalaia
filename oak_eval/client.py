from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import sleep, time
from typing import Any

import httpx

from .bundle import package_suite_bundle
from .comparison import compare_runs
from .core import ArtifactRef, CaseResult, ComparisonResult, EvalSuite, RunResult


@dataclass(slots=True)
class RunHandle:
    run_id: str
    client: "OakEvalClient"

    def refresh(self) -> RunResult:
        return self.client.get_run(self.run_id)

    def wait(self, timeout: float | None = None) -> RunResult:
        return self.client.wait_for_run(self.run_id, timeout=timeout)


class OakEvalClient:
    def __init__(self, *, base_url: str, token: str, client: Any | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._auth_header = {"Authorization": f"Bearer {token}"}
        self._client = client or httpx.Client(headers=self._auth_header)
        self._owns_client = client is None

    @classmethod
    def from_env(cls) -> "OakEvalClient":
        import os

        base_url = os.environ.get("OAK_EVAL_API_URL")
        token = os.environ.get("OAK_EVAL_TOKEN")
        if not base_url or not token:
            raise RuntimeError("OAK_EVAL_API_URL and OAK_EVAL_TOKEN must be set")
        return cls(base_url=base_url, token=token)

    def run(
        self,
        suite: EvalSuite,
        *,
        suite_spec: str,
        project_slug: str = "default",
        reference_run_id: str | None = None,
        wait: bool = False,
    ) -> RunHandle | RunResult:
        payload: dict[str, Any] = {
            "suite_spec": suite_spec,
            "project_slug": project_slug,
            "suite": {
                "name": suite.name,
                "description": suite.description,
                "metadata": suite.metadata,
                "cases": [
                    {
                        "id": case.id,
                        "input": case.input,
                        "expected": case.expected,
                        "metadata": case.metadata,
                    }
                    for case in suite.cases
                ],
            },
            "bundle": package_suite_bundle(suite_spec),
            "reference_run_id": reference_run_id,
        }
        response = self._request("POST", "/runs", json=payload)
        response.raise_for_status()
        data = response.json()
        run_id = str(data["run_id"])
        handle = RunHandle(run_id=run_id, client=self)
        if wait:
            return handle.wait()
        return handle

    def list_runs(self, *, status: str | None = None, project_slug: str | None = None) -> list[str]:
        params: dict[str, Any] = {}
        if status is not None:
            params["status_filter"] = status
        if project_slug is not None:
            params["project_slug"] = project_slug
        response = self._request("GET", "/runs", params=params)
        response.raise_for_status()
        return [str(item["run_id"]) for item in response.json()]

    def start_run(self, run_id: str) -> RunResult:
        response = self._request("POST", f"/runs/{run_id}/start")
        response.raise_for_status()
        return self._parse_run(response.json())

    def complete_run(self, run_id: str, result: RunResult) -> RunResult:
        response = self._request(
            "POST",
            f"/runs/{run_id}/complete",
            json=self._serialize_run_completion(result),
        )
        response.raise_for_status()
        return self._parse_run(response.json())

    def get_run(self, run_id: str) -> RunResult:
        response = self._request("GET", f"/runs/{run_id}")
        response.raise_for_status()
        return self._parse_run(response.json())

    def get_run_artifact(self, run_id: str, artifact_key: str) -> dict[str, Any]:
        response = self._request("GET", f"/runs/{run_id}/artifacts/{artifact_key}")
        response.raise_for_status()
        return dict(response.json())

    def wait_for_run(self, run_id: str, timeout: float | None = None) -> RunResult:
        deadline = None if timeout is None else (time() + timeout)
        while True:
            run = self.get_run(run_id)
            if run.status not in {"queued", "running"}:
                return run
            if deadline is not None and time() >= deadline:
                raise TimeoutError(f"run {run_id} did not finish within {timeout} seconds")
            sleep(0.5)

    def compare(self, current_run_id: str, reference_run_id: str) -> ComparisonResult:
        current = self.get_run(current_run_id)
        reference = self.get_run(reference_run_id)
        return compare_runs(current=current, reference=reference)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.update(self._auth_header)
        return self._client.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)

    def _parse_run(self, data: dict[str, Any]) -> RunResult:
        return RunResult(
            run_id=str(data["run_id"]),
            suite_name=str(data.get("suite_name", "remote-suite")),
            summary=data["summary"],
            metrics=data["metrics"],
            cases=[
                CaseResult(
                    case_id=str(case["case_id"]),
                    status=case["status"],
                    score=case.get("score"),
                    expected=case["expected"],
                    actual=case.get("actual"),
                    latency_ms=case.get("latency_ms"),
                    error=case.get("error"),
                )
                for case in data.get("cases", [])
            ],
            artifacts=[
                ArtifactRef(
                    artifact_id=str(artifact["artifact_id"]),
                    kind=artifact["kind"],
                    path=artifact.get("path"),
                    mime_type=artifact.get("mime_type"),
                )
                for artifact in data.get("artifacts", [])
            ],
            config=dict(data.get("config", {})),
            status=str(data.get("status", "completed")),
        )

    def _serialize_run_completion(self, result: RunResult) -> dict[str, Any]:
        return {
            "status": "completed" if result.passed else result.status,
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
                self._serialize_artifact(artifact)
                for artifact in result.artifacts
            ],
        }

    def _serialize_artifact(self, artifact: ArtifactRef) -> dict[str, Any]:
        payload: Any = None
        if artifact.path:
            path = Path(artifact.path)
            if path.exists() and path.is_file():
                try:
                    payload = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    payload = path.read_bytes().hex()
        return {
            "artifact_key": artifact.artifact_id.split(":", 1)[-1],
            "kind": artifact.kind,
            "path": artifact.path,
            "mime_type": artifact.mime_type,
            "payload": payload,
        }
