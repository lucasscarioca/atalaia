from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .core import run_local
from .loader import load_suite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oak-eval")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create evals/ and .oak-eval/")
    init_parser.add_argument("--force", action="store_true", help="Overwrite the sample suite")

    run_parser = subparsers.add_parser("run", help="Run a suite locally")
    run_parser.add_argument("--suite", required=True, help="Module path to an EvalSuite, e.g. evals.sample:suite")
    run_parser.add_argument("--json", action="store_true", help="Emit JSON output")
    run_parser.add_argument("--artifact-dir", default=".oak-eval", help="Artifact output directory")

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
        "passed": result.passed,
    }


def _cmd_run(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    result = run_local(suite, artifact_dir=args.artifact_dir)
    if args.json:
        print(json.dumps(_serialize_result(result), indent=2, sort_keys=True))
    else:
        print(f"suite={result.suite_name} run_id={result.run_id}")
        print(
            f"total={result.summary['total']} passed={result.summary['passed']} "
            f"failed={result.summary['failed']} error={result.summary['error']}"
        )
        for case in result.cases:
            print(f"- {case.case_id}: {case.status}")
    return 0 if result.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return _cmd_init(args.force)
    if args.command == "run":
        return _cmd_run(args)
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
