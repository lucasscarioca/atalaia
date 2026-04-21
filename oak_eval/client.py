from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .comparison import compare_runs
from .core import ComparisonResult, EvalSuite, RunResult


@dataclass(slots=True)
class RunHandle:
    run_id: str
    client: "OakEvalClient"

    def refresh(self) -> RunResult:
        return self.client.get_run(self.run_id)

    def wait(self, timeout: float | None = None) -> RunResult:
        return self.client.wait_for_run(self.run_id, timeout=timeout)


class OakEvalClient:
    def __init__(self, *, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(headers={"Authorization": f"Bearer {token}"})

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
        reference_run_id: str | None = None,
        wait: bool = False,
    ) -> RunHandle | RunResult:
        payload: dict[str, Any] = {
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
            "reference_run_id": reference_run_id,
        }
        response = self._client.post(f"{self.base_url}/runs", json=payload)
        response.raise_for_status()
        data = response.json()
        run_id = str(data["run_id"])
        handle = RunHandle(run_id=run_id, client=self)
        if wait:
            return handle.wait()
        return handle

    def get_run(self, run_id: str) -> RunResult:
        response = self._client.get(f"{self.base_url}/runs/{run_id}")
        response.raise_for_status()
        data = response.json()
        return RunResult(
            run_id=data["run_id"],
            suite_name=data["suite_name"],
            summary=data["summary"],
            metrics=data["metrics"],
            cases=[],
            artifacts=[],
        )

    def wait_for_run(self, run_id: str, timeout: float | None = None) -> RunResult:
        _ = timeout
        return self.get_run(run_id)

    def compare(self, current_run_id: str, reference_run_id: str) -> ComparisonResult:
        current = self.get_run(current_run_id)
        reference = self.get_run(reference_run_id)
        return compare_runs(current=current, reference=reference)
