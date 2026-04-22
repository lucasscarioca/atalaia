# oak-eval

Git-native, self-hosted evals-as-code for AI agents.

oak-eval lets you define eval suites in Git, run them locally for fast feedback, and execute them remotely on your own server for CI gating and shared regression checks.

## Core concepts

- **Project** — a repository or workspace that owns suites and runs
- **Eval Suite** — Python code that defines cases and checks
- **Case** — one input / expected pair plus the assertion logic that validates it
- **Run** — one execution of a suite
- **Adapter** — the interface a case uses to call a model, service, or HTTP target
- **Artifact** — files or payloads produced by a run
- **Reference run** — a prior run used for comparison and regression checks

## Repo layout

- `evals/` — suite code you author and review in Git
- `.oak-eval/` — local tool state and generated artifacts
- `oak_eval/` — Python SDK, CLI, worker, and adapters
- `app/` — self-hosted API and persistence layer
- `docs/` — public docs for users of the project

## Quickstart

```bash
uv sync --dev
uv run oak-eval init
uv run oak-eval run --suite evals.sample:suite
```

That gives you a local sample suite you can edit under `evals/sample.py`.

## Local workflow

Run a suite locally for fast feedback:

```bash
uv run oak-eval run --suite evals.sample:suite
uv run oak-eval run --suite evals.sample:suite --min-accuracy 0.95
uv run oak-eval check --run-id <run-id> --against <reference-run-id>
```

Author suites in Python:

```python
from oak_eval import EvalContext, EvalSuite

suite = EvalSuite(name="sample", adapter=MyAdapter())

@suite.case(id="case-1", input={"text": "label:ok"}, expected={"label": "ok"})
def check_case(ctx: EvalContext) -> None:
    actual = ctx.adapter.invoke(ctx.case.input)
    assert actual["label"] == ctx.case.expected["label"]
```

## Remote workflow

Submit a suite to your self-hosted API, then let a worker process queued runs:

```bash
uv run oak-eval run --suite evals.sample:suite --remote --wait
uv run oak-eval worker
```

Remote runs automatically package and upload the suite bundle. The worker pulls the queued run, loads the bundle, executes the suite locally, and posts the results back to the API.

## HTTP adapter

For suites that exercise a live service, use `oak_eval.adapters.http.HTTPAdapter`.

## CI examples

The repo includes minimal examples for:

- GitHub Actions: `.github/workflows/oak-eval-ci-example.yml`
- GitLab CI: `.gitlab-ci.yml.example`

Both examples run the local suite and can optionally run a remote regression check when these variables are set:

- `OAK_EVAL_API_URL`
- `OAK_EVAL_TOKEN`
- `OAK_EVAL_PROJECT_SLUG`
- `OAK_EVAL_REFERENCE_RUN_ID`

## Public docs

Start at `docs/README.md` for the public documentation index.
