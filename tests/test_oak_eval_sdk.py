from __future__ import annotations

from dataclasses import dataclass

import oak_eval.cli as cli_module
from oak_eval import ArtifactRef, CaseResult, EvalContext, EvalSuite, RunResult, compare_runs, load_suite, run_local
from oak_eval.bundle import load_suite_from_bundle, package_suite_bundle
from oak_eval.checks import evaluate_run_thresholds
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
