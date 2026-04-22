from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from time import sleep
from typing import Any

from .checks import ThresholdReport, evaluate_comparison_thresholds, evaluate_run_thresholds
from .client import OakEvalClient
from .core import run_local
from .loader import load_suite
from .worker import OakEvalWorker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oak-eval")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create evals/ and .oak-eval/")
    init_parser.add_argument("--force", action="store_true", help="Overwrite the sample suite")

    run_parser = subparsers.add_parser("run", help="Run a suite locally or submit it to a remote server")
    run_parser.add_argument("--suite", required=True, help="Module path to an EvalSuite, e.g. evals.sample:suite")
    run_parser.add_argument("--json", action="store_true", help="Emit JSON output")
    run_parser.add_argument("--artifact-dir", default=".oak-eval", help="Artifact output directory")
    run_parser.add_argument("--remote", action="store_true", help="Submit the suite to a remote server")
    run_parser.add_argument("--wait", action="store_true", help="Wait for remote completion")
    run_parser.add_argument("--api-url", help="Remote API URL")
    run_parser.add_argument("--token", help="Remote API token")
    run_parser.add_argument("--project-slug", default="default", help="Remote project slug")
    run_parser.add_argument("--min-pass-rate", type=float, help="Fail if pass rate drops below this value")
    run_parser.add_argument("--min-accuracy", type=float, help="Fail if accuracy drops below this value")

    check_parser = subparsers.add_parser("check", help="Evaluate thresholds for a completed run")
    check_parser.add_argument("--run-id", required=True, help="Current run ID to check")
    check_parser.add_argument("--against", help="Reference run ID to compare against")
    check_parser.add_argument("--json", action="store_true", help="Emit JSON output")
    check_parser.add_argument("--api-url", help="Remote API URL")
    check_parser.add_argument("--token", help="Remote API token")
    check_parser.add_argument("--min-pass-rate", type=float, help="Fail if pass rate drops below this value")
    check_parser.add_argument("--min-accuracy", type=float, help="Fail if accuracy drops below this value")
    check_parser.add_argument("--max-failed-delta", type=int, help="Fail if failed cases increase above this value")
    check_parser.add_argument("--max-error-delta", type=int, help="Fail if errors increase above this value")
    check_parser.add_argument("--min-accuracy-delta", type=float, help="Fail if accuracy delta drops below this value")

    worker_parser = subparsers.add_parser("worker", help="Poll remote runs and execute queued suites")
    worker_parser.add_argument("--once", action="store_true", help="Process queued runs once and exit")
    worker_parser.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between polls")
    worker_parser.add_argument("--api-url", help="Remote API URL")
    worker_parser.add_argument("--token", help="Remote API token")

    return parser


def _cmd_init(force: bool) -> int:
    evals_dir = Path("evals")
    state_dir = Path(".oak-eval")
    evals_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    init_file = evals_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")

    sample = evals_dir / "sample.py"
    if force or not sample.exists():
        sample.write_text(
            "from oak_eval import EvalSuite, EvalContext\n\n"
            "class LocalAdapter:\n"
            "    def invoke(self, payload):\n"
            "        return {'label': str(payload['text']).removeprefix('label:')}\n\n"
            "suite = EvalSuite(name='sample', adapter=LocalAdapter())\n\n"
            "@suite.case(id='example', input={'text': 'label:ok'}, expected={'label': 'ok'})\n"
            "def check_example(ctx: EvalContext) -> None:\n"
            "    actual = ctx.adapter.invoke(ctx.case.input)\n"
            "    assert actual['label'] == ctx.case.expected['label']\n",
            encoding="utf-8",
        )

    return 0


def _serialize_result(result: Any) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "suite_name": result.suite_name,
        "summary": result.summary,
        "metrics": result.metrics,
        "cases": [asdict(case) for case in result.cases],
        "artifacts": [asdict(artifact) for artifact in result.artifacts],
        "config": getattr(result, "config", {}),
        "status": getattr(result, "status", "completed"),
        "passed": result.passed,
    }


def _serialize_threshold_report(report: Any) -> dict[str, Any]:
    return {
        "passed": report.passed,
        "reasons": report.reasons,
        "details": report.details,
    }


def _resolve_client(args: argparse.Namespace) -> OakEvalClient:
    if args.api_url and args.token:
        return OakEvalClient(base_url=args.api_url, token=args.token)
    if args.api_url or args.token:
        raise RuntimeError("provide both --api-url and --token, or neither to use env vars")
    return OakEvalClient.from_env()


def _print_result(result: Any) -> None:
    print(f"suite={result.suite_name} run_id={result.run_id}")
    print(
        f"total={result.summary['total']} passed={result.summary['passed']} "
        f"failed={result.summary['failed']} error={result.summary['error']}"
    )
    for case in result.cases:
        print(f"- {case.case_id}: {case.status}")


def _print_threshold_report(report: Any) -> None:
    if report.passed:
        print("thresholds=passed")
        return
    print("thresholds=failed")
    for reason in report.reasons:
        print(f"! {reason}")


def _cmd_run(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    if args.remote:
        client = _resolve_client(args)
        wait_for_result = args.wait or args.min_pass_rate is not None or args.min_accuracy is not None
        outcome = client.run(
            suite,
            suite_spec=args.suite,
            project_slug=args.project_slug,
            wait=wait_for_result,
        )
        if isinstance(outcome, str):  # pragma: no cover - defensive
            print(outcome)
            return 0
        if hasattr(outcome, "run_id") and not hasattr(outcome, "summary"):
            print(f"submitted run_id={outcome.run_id}")
            return 0
        threshold_report = evaluate_run_thresholds(
            outcome,
            min_pass_rate=args.min_pass_rate,
            min_accuracy=args.min_accuracy,
        )
        if args.json:
            payload = _serialize_result(outcome)
            payload["thresholds"] = _serialize_threshold_report(threshold_report)
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            _print_result(outcome)
            _print_threshold_report(threshold_report)
        return 0 if outcome.passed and threshold_report.passed else 1

    result = run_local(suite, artifact_dir=args.artifact_dir)
    threshold_report = evaluate_run_thresholds(
        result,
        min_pass_rate=args.min_pass_rate,
        min_accuracy=args.min_accuracy,
    )
    if args.json:
        payload = _serialize_result(result)
        payload["thresholds"] = _serialize_threshold_report(threshold_report)
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_result(result)
        _print_threshold_report(threshold_report)
    return 0 if result.passed and threshold_report.passed else 1


def _cmd_check(args: argparse.Namespace) -> int:
    client = _resolve_client(args)
    current = client.get_run(args.run_id)

    threshold_report = evaluate_run_thresholds(
        current,
        min_pass_rate=args.min_pass_rate,
        min_accuracy=args.min_accuracy,
    )

    comparison_report = None
    if args.against:
        reference = client.get_run(args.against)
        comparison_report = evaluate_comparison_thresholds(
            current,
            reference,
            max_failed_delta=args.max_failed_delta,
            max_error_delta=args.max_error_delta,
            min_accuracy_delta=args.min_accuracy_delta,
        )
        threshold_report = ThresholdReport(
            passed=threshold_report.passed and comparison_report.passed,
            reasons=[*threshold_report.reasons, *comparison_report.reasons],
            details={
                **threshold_report.details,
                "comparison": comparison_report.details,
            },
        )

    if args.json:
        payload = _serialize_result(current)
        payload["thresholds"] = _serialize_threshold_report(threshold_report)
        if comparison_report is not None:
            payload["comparison"] = comparison_report.details
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_result(current)
        if comparison_report is not None:
            print(f"against={args.against}")
            print(
                f"failed_delta={comparison_report.details.get('failed_delta', 0)} "
                f"error_delta={comparison_report.details.get('error_delta', 0)}"
            )
            if "accuracy_delta" in comparison_report.details:
                print(f"accuracy_delta={comparison_report.details['accuracy_delta']}")
        _print_threshold_report(threshold_report)
    return 0 if threshold_report.passed else 1


def _cmd_worker(args: argparse.Namespace) -> int:
    if args.api_url and args.token:
        worker = OakEvalWorker(client=OakEvalClient(base_url=args.api_url, token=args.token))
    elif args.api_url or args.token:
        raise RuntimeError("provide both --api-url and --token, or neither to use env vars")
    else:
        worker = OakEvalWorker.from_env()

    if args.once:
        processed = worker.process_once()
        print(f"processed={processed}")
        return 0

    while True:
        processed = worker.process_once()
        print(f"processed={processed}")
        sleep(args.poll_interval)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return _cmd_init(args.force)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "check":
        return _cmd_check(args)
    if args.command == "worker":
        return _cmd_worker(args)
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
