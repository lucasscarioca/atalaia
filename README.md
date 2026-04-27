# oak-eval

Git-native, self-hosted evals-as-code for AI agents.

Define suites in Git, run them locally for fast feedback, or run them remotely on your own server for CI gating and regression checks.

## What you get

- Suites live under `evals/`
- Local state and artifacts live under `.oak-eval/`
- Python SDK first, CLI on top
- Local runs, remote runs, reference-run comparisons
- Threshold checks with non-zero exits
- HTTP adapter for live services

## Quickstart

```bash
uv sync --dev
uv run oak-eval init
uv run oak-eval run --suite evals.sample:suite
```

That gives you a working sample suite in `evals/sample.py`.

## Demo path

Local loop:

```bash
uv run oak-eval run --suite evals.sample:suite
uv run oak-eval run --suite evals.sample:suite --min-accuracy 0.95
```

Remote loop with Docker:

```bash
docker compose up --build
```

This starts Postgres, the API, and a worker. In another terminal, create an API token and submit a remote run:

```bash
export OAK_EVAL_API_URL=http://localhost:8000
export OAK_EVAL_TOKEN=$(curl -s -X POST "$OAK_EVAL_API_URL/tokens" \
  -H "Content-Type: application/json" \
  -H "X-Oak-Eval-Admin-Token: ${OAK_EVAL_BOOTSTRAP_TOKEN:-dev-bootstrap}" \
  -d '{"name":"local-cli"}' | python -c 'import json,sys; print(json.load(sys.stdin)["token"])')
uv run oak-eval run --suite evals.sample:suite --remote --wait
```

Compare a remote run against a reference run:

```bash
uv run oak-eval check --run-id <run-id> --against <reference-run-id>
```

CI loop:

```bash
uv run oak-eval run --suite evals.sample:suite --min-accuracy 0.95
uv run oak-eval run --suite evals.sample:suite --remote --wait
uv run oak-eval check --run-id <run-id> --against <reference-run-id>
```

`<reference-run-id>` is just a previous successful run ID from the API.

## Write a suite

```python
from oak_eval import EvalContext, EvalSuite

suite = EvalSuite(name="sample", adapter=MyAdapter())

@suite.case(id="case-1", input={"text": "label:ok"}, expected={"label": "ok"})
def check_case(ctx: EvalContext) -> None:
    actual = ctx.adapter.invoke(ctx.case.input)
    assert actual["label"] == ctx.case.expected["label"]
```

## Run it

Local:

```bash
uv run oak-eval run --suite evals.sample:suite
uv run oak-eval run --suite evals.sample:suite --min-accuracy 0.95
uv run oak-eval check --run-id <run-id> --against <reference-run-id>
```

Remote:

```bash
docker compose up --build
uv run oak-eval run --suite evals.sample:suite --remote --wait
```

Remote runs upload the suite bundle automatically. The Docker worker picks up queued runs, loads the bundle, runs the suite, and posts results back. If you are not using Docker, run `uv run oak-eval worker` as a separate long-lived process on the self-hosted machine.

## CI examples

- GitHub Actions: `.github/workflows/oak-eval-ci-example.yml`
- GitLab CI: `.gitlab-ci.yml.example`

Both examples run the local suite and can optionally run a remote regression check when these variables are set:

- `OAK_EVAL_API_URL`
- `OAK_EVAL_TOKEN`
- `OAK_EVAL_PROJECT_SLUG`
- `OAK_EVAL_REFERENCE_RUN_ID`

## Public docs

Start at `docs/README.md` if you want a tiny docs index.
