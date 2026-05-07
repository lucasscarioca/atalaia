from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from .bundle import open_suite_bundle
from .client import AtalaiaClient
from .core import ArtifactRef, CaseResult, RunResult, run_local


@dataclass(slots=True)
class AtalaiaWorker:
    client: AtalaiaClient

    @classmethod
    def from_env(cls) -> AtalaiaWorker:
        return cls(client=AtalaiaClient.from_env())

    def process_once(self) -> int:
        processed = 0
        for run_id in self.client.list_runs(status="queued"):
            self.process_run(run_id)
            processed += 1
        return processed

    def process_run(self, run_id: str) -> RunResult:
        run = self.client.get_run(run_id)
        suite_spec = run.config.get("suite_spec")
        if not isinstance(suite_spec, str) or not suite_spec:
            return self._fail_run(run, error=f"run {run_id} is missing suite_spec")

        try:
            self.client.start_run(run_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                return self.client.get_run(run_id)
            raise

        try:
            bundle = run.config.get("bundle")
            if not (isinstance(bundle, dict) and bundle.get("archive_base64")):
                artifact = self.client.get_run_artifact(run_id, "suite.bundle")
                payload = artifact.get("payload") if isinstance(artifact, dict) else None
                if isinstance(payload, dict) and payload.get("archive_base64"):
                    bundle = payload
                elif isinstance(payload, dict) and payload.get("bundle"):
                    bundle = payload["bundle"]
                else:
                    bundle = payload
            if not (isinstance(bundle, dict) and bundle.get("archive_base64")):
                raise RuntimeError(f"run {run_id} is missing a usable suite bundle")

            with open_suite_bundle(bundle) as suite, TemporaryDirectory() as tmpdir:
                artifact_dir = Path(tmpdir) / "artifacts"
                result = run_local(suite, artifact_dir=artifact_dir)
                try:
                    return self.client.complete_run(run_id, result)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 409:
                        return self.client.get_run(run_id)
                    raise
        except Exception as exc:  # pragma: no cover - exercised in integration failure paths
            return self._fail_run(run, error=f"{exc.__class__.__name__}: {exc}")

    def _fail_run(self, run: RunResult, *, error: str) -> RunResult:
        failure = RunResult(
            run_id=run.run_id,
            suite_name=run.suite_name,
            summary={"total": 0, "passed": 0, "failed": 0, "error": 1, "invalid_case": 0},
            metrics={"accuracy": None, "average_latency_ms": None},
            cases=[
                CaseResult(
                    case_id="worker",
                    status="error",
                    score=None,
                    expected={},
                    actual=None,
                    latency_ms=None,
                    error=error,
                )
            ],
            artifacts=[
                ArtifactRef(
                    artifact_id=f"{run.run_id}:worker.log",
                    kind="error",
                    path=None,
                    mime_type="text/plain",
                )
            ],
            config=run.config,
            status="failed",
        )
        return self.client.complete_run(run.run_id, failure)
