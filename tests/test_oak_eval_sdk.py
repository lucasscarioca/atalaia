from __future__ import annotations

from dataclasses import dataclass

from oak_eval import EvalContext, EvalSuite, compare_runs, load_suite, run_local


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
