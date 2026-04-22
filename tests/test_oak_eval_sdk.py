from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from pathlib import Path
import base64
import binascii
import io
import json
from zipfile import ZipFile

import oak_eval.cli as cli_module
from oak_eval import ArtifactRef, CaseResult, EvalContext, EvalSuite, RunResult, compare_runs, load_suite, run_local
from oak_eval.adapters.http import HTTPAdapter
from oak_eval.bundle import load_suite_from_bundle, open_suite_bundle, package_suite_bundle
from oak_eval.checks import evaluate_comparison_thresholds, evaluate_run_thresholds
from oak_eval.client import OakEvalClient
from oak_eval.cli import main as oak_eval_main


@dataclass
class DummyAdapter:
    def invoke(self, payload: dict[str, object]) -> dict[str, object]:
        text = str(payload["text"])
        if text.startswith("label:"):
            return {"label": text.removeprefix("label:")}
        return {"label": "unknown"}


def test_run_local_executes_suite_cases(tmp_path) -> None:
    suite = EvalSuite(name="demo", adapter=DummyAdapter())

    @suite.case(
        id="passes",
        input={"text": "label:pass"},
        expected={"label": "pass"},
    )
    def check_pass(ctx: EvalContext) -> None:
        actual = ctx.adapter.invoke(ctx.case.input)
        assert actual["label"] == ctx.case.expected["label"]

    @suite.case(
        id="fails",
        input={"text": "label:fail"},
        expected={"label": "expected"},
    )
    def check_fail(ctx: EvalContext) -> None:
        actual = ctx.adapter.invoke(ctx.case.input)
        assert actual["label"] == ctx.case.expected["label"]

    result = run_local(suite, artifact_dir=tmp_path)

    assert result.run_id
    assert result.suite_name == "demo"
    assert result.summary == {"total": 2, "passed": 1, "failed": 1, "error": 0, "invalid_case": 0}
    assert result.passed is False


def test_load_suite_can_import_the_repo_sample_suite() -> None:
    suite = load_suite("evals.sample:suite")

    assert suite.name == "sample"
    assert len(suite.cases) == 1


def test_suite_bundle_roundtrip_loads_the_sample_suite() -> None:
    bundle = package_suite_bundle("evals.sample:suite")
    suite = load_suite_from_bundle(bundle)

    assert suite.name == "sample"
    assert len(suite.cases) == 1


def test_suite_bundle_supports_top_level_modules(tmp_path, monkeypatch) -> None:
    module_path = tmp_path / "flat_eval.py"
    module_path.write_text(
        "from oak_eval import EvalContext, EvalSuite\n"
        "suite = EvalSuite(name='flat', adapter=object())\n"
        "@suite.case(id='flat-case', input={'text': 'x'}, expected={'label': 'ok'})\n"
        "def check_flat(ctx: EvalContext) -> None:\n"
        "    assert ctx.case.expected['label'] == 'ok'\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    bundle = package_suite_bundle("flat_eval:suite")
    suite = load_suite_from_bundle(bundle)

    assert suite.name == "flat"
    assert len(suite.cases) == 1


def test_suite_bundle_context_keeps_files_available_during_execution(tmp_path, monkeypatch) -> None:
    package_dir = tmp_path / "lazy_suite"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        "from oak_eval import EvalContext, EvalSuite\n"
        "from pathlib import Path\n"
        "suite = EvalSuite(name='lazy', adapter=object())\n"
        "@suite.case(id='reads-data', input={'text': 'x'}, expected={'label': 'ok'})\n"
        "def check_lazy(ctx: EvalContext) -> None:\n"
        "    data = Path(__file__).with_name('data.txt').read_text(encoding='utf-8').strip()\n"
        "    assert data == 'ok'\n",
        encoding="utf-8",
    )
    (package_dir / "data.txt").write_text("ok\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    bundle = package_suite_bundle("lazy_suite:suite")
    with open_suite_bundle(bundle) as suite:
        result = run_local(suite, artifact_dir=tmp_path)

    assert result.passed is True


def test_bundle_rejects_unsafe_zip_paths(tmp_path) -> None:
    archive = io.BytesIO()
    with ZipFile(archive, "w") as zf:
        zf.writestr("../escape.py", "raise SystemExit('nope')\n")
        zf.writestr("flat_eval.py", "from oak_eval import EvalSuite\nsuite = EvalSuite(name='flat', adapter=object())\n")

    bundle = {
        "format": "zip",
        "module_name": "flat_eval",
        "object_name": "suite",
        "package_name": "flat_eval",
        "archive_base64": base64.b64encode(archive.getvalue()).decode("ascii"),
    }

    try:
        load_suite_from_bundle(bundle)
    except ValueError as exc:
        assert "unsafe archive paths" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected unsafe bundle to be rejected")


def test_load_suite_from_bundle_rejects_malformed_payloads() -> None:
    malformed_bundles = [
        ({"format": "tar"}, "unsupported suite bundle format"),
        (
            {
                "format": "zip",
                "module_name": "flat_eval",
                "object_name": "suite",
                "package_name": "flat_eval",
            },
            "bundle is missing archive_base64",
        ),
    ]
    for bundle, message in malformed_bundles:
        try:
            load_suite_from_bundle(bundle)
        except ValueError as exc:
            assert message in str(exc)
        else:  # pragma: no cover - defensive
            raise AssertionError(f"expected {message!r}")

    try:
        load_suite_from_bundle(
            {
                "format": "zip",
                "module_name": "flat_eval",
                "object_name": "suite",
                "package_name": "flat_eval",
                "archive_base64": "not-base64!!",
            }
        )
    except Exception as exc:
        assert isinstance(exc, (binascii.Error, ValueError))
    else:  # pragma: no cover - defensive
        raise AssertionError("expected malformed base64 bundle to fail")


def test_wait_for_run_polls_until_completion(monkeypatch) -> None:
    client = OakEvalClient(base_url="http://example.test", token="token", client=object())
    statuses = ["queued", "running", "completed"]

    def fake_get_run(run_id: str) -> RunResult:
        status = statuses.pop(0)
        return RunResult(
            run_id=run_id,
            suite_name="demo",
            summary={"total": 1, "passed": 1, "failed": 0, "error": 0, "invalid_case": 0},
            metrics={"accuracy": 1.0, "average_latency_ms": 1},
            cases=[],
            artifacts=[],
            status=status,
        )

    monkeypatch.setattr(client, "get_run", fake_get_run)
    monkeypatch.setattr("oak_eval.client.sleep", lambda _: None)

    result = client.wait_for_run("run-1", timeout=1)

    assert result.status == "completed"
    assert statuses == []


def test_http_adapter_runs_against_a_live_http_service(tmp_path) -> None:
    received_requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8"))
            received_requests.append(payload)
            assert payload["input"]["text"] == "label:ok"
            response = {"label": payload["input"]["text"].removeprefix("label:")}
            encoded = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        adapter = HTTPAdapter(base_url=f"http://{host}:{port}", path="/invoke")
        suite = EvalSuite(name="http", adapter=adapter)

        @suite.case(id="invokes-http-service", input={"text": "label:ok"}, expected={"label": "ok"})
        def check_http(ctx: EvalContext) -> None:
            actual = ctx.adapter.invoke(ctx.case.input)
            assert actual["label"] == ctx.case.expected["label"]

        result = run_local(suite, artifact_dir=tmp_path)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert result.passed is True
    assert result.summary == {"total": 1, "passed": 1, "failed": 0, "error": 0, "invalid_case": 0}
    assert received_requests and received_requests[0]["input"]["text"] == "label:ok"


def test_compare_runs_reports_case_and_summary_deltas(tmp_path) -> None:
    suite = EvalSuite(name="demo", adapter=DummyAdapter())

    @suite.case(id="pass", input={"text": "label:pass"}, expected={"label": "pass"})
    def check_pass(ctx: EvalContext) -> None:
        actual = ctx.adapter.invoke(ctx.case.input)
        assert actual["label"] == ctx.case.expected["label"]

    @suite.case(id="fail", input={"text": "label:fail"}, expected={"label": "expected"})
    def check_fail(ctx: EvalContext) -> None:
        actual = ctx.adapter.invoke(ctx.case.input)
        assert actual["label"] == ctx.case.expected["label"]

    reference = run_local(suite, artifact_dir=tmp_path)
    current = run_local(suite, artifact_dir=tmp_path)
    comparison = compare_runs(current=current, reference=reference)

    assert comparison.current_run_id == current.run_id
    assert comparison.reference_run_id == reference.run_id
    assert comparison.summary_delta == {"error": 0, "failed": 0, "invalid_case": 0, "passed": 0, "total": 0}
    assert {delta.case_id for delta in comparison.case_deltas} == {"pass", "fail"}


def test_evaluate_run_thresholds_treats_empty_runs_as_full_pass_rate() -> None:
    result = RunResult(
        run_id="empty",
        suite_name="demo",
        summary={"total": 0, "passed": 0, "failed": 0, "error": 0, "invalid_case": 0},
        metrics={"accuracy": None, "average_latency_ms": None},
        cases=[],
        artifacts=[],
    )

    report = evaluate_run_thresholds(result, min_pass_rate=1.0)

    assert report.passed is True
    assert report.details["pass_rate"] == 1.0


def test_evaluate_run_thresholds_flags_missing_accuracy_metric() -> None:
    result = RunResult(
        run_id="missing-accuracy",
        suite_name="demo",
        summary={"total": 1, "passed": 1, "failed": 0, "error": 0, "invalid_case": 0},
        metrics={"accuracy": None, "average_latency_ms": None},
        cases=[],
        artifacts=[],
    )

    report = evaluate_run_thresholds(result, min_accuracy=0.5)

    assert report.passed is False
    assert "unavailable" in report.reasons[0]


def test_evaluate_comparison_thresholds_cover_boundaries_and_details() -> None:
    current = RunResult(
        run_id="current",
        suite_name="demo",
        summary={"total": 1, "passed": 0, "failed": 1, "error": 0, "invalid_case": 0},
        metrics={"accuracy": 0.5, "average_latency_ms": 1},
        cases=[
            CaseResult(
                case_id="case-1",
                status="failed",
                score=0.5,
                expected={"label": "ok"},
                actual={"label": "bad"},
                latency_ms=1,
                error="boom",
            )
        ],
        artifacts=[],
    )
    reference = RunResult(
        run_id="reference",
        suite_name="demo",
        summary={"total": 1, "passed": 1, "failed": 0, "error": 0, "invalid_case": 0},
        metrics={"accuracy": 0.5, "average_latency_ms": 1},
        cases=[
            CaseResult(
                case_id="case-1",
                status="passed",
                score=0.5,
                expected={"label": "ok"},
                actual=None,
                latency_ms=1,
                error=None,
            )
        ],
        artifacts=[],
    )

    report = evaluate_comparison_thresholds(
        current,
        reference,
        max_failed_delta=1,
        max_error_delta=0,
        min_accuracy_delta=0.0,
    )

    assert report.passed is True
    assert report.details["failed_delta"] == 1
    assert report.details["error_delta"] == 0
    assert report.details["accuracy_delta"] == 0.0
    assert report.details["case_deltas"][0]["current_status"] == "failed"
    assert report.details["case_deltas"][0]["reference_status"] == "passed"


def test_evaluate_comparison_thresholds_fail_when_accuracy_is_unavailable() -> None:
    current = RunResult(
        run_id="current",
        suite_name="demo",
        summary={"total": 1, "passed": 1, "failed": 0, "error": 0, "invalid_case": 0},
        metrics={"accuracy": None, "average_latency_ms": 1},
        cases=[],
        artifacts=[],
    )
    reference = RunResult(
        run_id="reference",
        suite_name="demo",
        summary={"total": 1, "passed": 1, "failed": 0, "error": 0, "invalid_case": 0},
        metrics={"accuracy": 1.0, "average_latency_ms": 1},
        cases=[],
        artifacts=[],
    )

    report = evaluate_comparison_thresholds(current, reference, min_accuracy_delta=0.0)

    assert report.passed is False
    assert "unavailable" in report.reasons[0]


def test_threshold_evaluation_can_fail_a_passing_run(tmp_path) -> None:
    suite = EvalSuite(name="thresholds", adapter=DummyAdapter())

    @suite.case(id="pass", input={"text": "label:pass"}, expected={"label": "pass"})
    def check_pass(ctx: EvalContext) -> None:
        actual = ctx.adapter.invoke(ctx.case.input)
        assert actual["label"] == ctx.case.expected["label"]

    result = run_local(suite, artifact_dir=tmp_path)
    report = evaluate_run_thresholds(result, min_accuracy=1.1)

    assert result.passed is True
    assert report.passed is False
    assert report.reasons


def test_cli_run_exits_non_zero_when_thresholds_fail() -> None:
    exit_code = oak_eval_main([
        "run",
        "--suite",
        "evals.sample:suite",
        "--min-accuracy",
        "1.1",
    ])

    assert exit_code == 1


def test_cli_remote_run_json_emits_submission_payload(monkeypatch, capsys) -> None:
    class FakeHandle:
        run_id = "queued-1"

    class FakeClient:
        def run(self, *args, **kwargs):
            return FakeHandle()

    monkeypatch.setattr(cli_module, "_resolve_client", lambda args: FakeClient())

    exit_code = oak_eval_main([
        "run",
        "--suite",
        "evals.sample:suite",
        "--remote",
        "--json",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"run_id": "queued-1", "status": "queued"}


def test_cli_check_rejects_comparison_thresholds_without_reference(monkeypatch, capsys) -> None:
    class FakeClient:
        def get_run(self, run_id: str) -> RunResult:
            return RunResult(
                run_id=run_id,
                suite_name="demo",
                summary={"total": 1, "passed": 1, "failed": 0, "error": 0, "invalid_case": 0},
                metrics={"accuracy": 1.0, "average_latency_ms": 1},
                cases=[],
                artifacts=[],
            )

    monkeypatch.setattr(cli_module, "_resolve_client", lambda args: FakeClient())

    exit_code = oak_eval_main([
        "check",
        "--run-id",
        "current",
        "--max-failed-delta",
        "0",
    ])

    assert exit_code == 2
    assert "comparison thresholds require --against" in capsys.readouterr().err


def test_cli_check_exits_non_zero_for_regression(monkeypatch) -> None:
    current = RunResult(
        run_id="current",
        suite_name="demo",
        summary={"total": 1, "passed": 0, "failed": 1, "error": 0, "invalid_case": 0},
        metrics={"accuracy": 0.0, "average_latency_ms": 1},
        cases=[
            CaseResult(
                case_id="case-1",
                status="failed",
                score=0.0,
                expected={"label": "ok"},
                actual={"label": "bad"},
                latency_ms=1,
                error="boom",
            )
        ],
        artifacts=[ArtifactRef(artifact_id="current:summary.json", kind="summary", path=None, mime_type="application/json")],
    )
    reference = RunResult(
        run_id="reference",
        suite_name="demo",
        summary={"total": 1, "passed": 1, "failed": 0, "error": 0, "invalid_case": 0},
        metrics={"accuracy": 1.0, "average_latency_ms": 1},
        cases=[
            CaseResult(
                case_id="case-1",
                status="passed",
                score=1.0,
                expected={"label": "ok"},
                actual=None,
                latency_ms=1,
                error=None,
            )
        ],
        artifacts=[ArtifactRef(artifact_id="reference:summary.json", kind="summary", path=None, mime_type="application/json")],
    )

    class FakeClient:
        def get_run(self, run_id: str) -> RunResult:
            return current if run_id == "current" else reference

    monkeypatch.setattr(cli_module, "_resolve_client", lambda args: FakeClient())

    exit_code = oak_eval_main([
        "check",
        "--run-id",
        "current",
        "--against",
        "reference",
        "--max-failed-delta",
        "0",
    ])

    assert exit_code == 1
