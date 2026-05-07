# Atalaia

Git-native, self-hosted evals-as-code for AI agents.

Define suites in Git, run them locally for fast feedback, or run them remotely on your own server for CI gating and regression checks.

## What you get

- Suites live under `evals/`
- Local state and artifacts live under `.Atalaia/`
- Python SDK first, CLI on top
- Local runs, remote runs, reference-run comparisons
- Threshold checks with non-zero exits
- HTTP adapter for live services

## Quickstart

```bash
uv sync --dev
uv run atal init
uv run atal run --suite evals.sample:suite
```

That gives you a working sample suite in `evals/sample.py`.

## Development checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Format code with:

```bash
uv run ruff format .
```

## Demo path

Local loop:

```bash
uv run atal run --suite evals.sample:suite
uv run atal run --suite evals.sample:suite --min-accuracy 0.95
```

Remote loop with Docker:

```bash
docker compose up --build
```

This starts Postgres, the API, and a worker. In another terminal, create an API token and submit a remote run:

```bash
export ATALAIA_API_URL=http://localhost:8000
export ATALAIA_TOKEN=$(curl -s -X POST "$ATALAIA_API_URL/tokens" \
  -H "Content-Type: application/json" \
  -H "X-Atalaia-Admin-Token: ${ATALAIA_BOOTSTRAP_TOKEN:-dev-bootstrap}" \
  -d '{"name":"local-cli"}' | python -c 'import json,sys; print(json.load(sys.stdin)["token"])')
uv run atal run --suite evals.sample:suite --remote --wait
```

Compare a remote run against a reference run:

```bash
uv run atal check --run-id <run-id> --against <reference-run-id>
```

CI loop:

```bash
uv run atal run --suite evals.sample:suite --min-accuracy 0.95
uv run atal run --suite evals.sample:suite --remote --wait
uv run atal check --run-id <run-id> --against <reference-run-id>
```

`<reference-run-id>` is just a previous successful run ID from the API.

## Write a suite

```python
from atalaia import EvalContext, EvalSuite

suite = EvalSuite(name="sample", adapter=MyAdapter())

@suite.case(id="case-1", input={"text": "label:ok"}, expected={"label": "ok"})
def check_case(ctx: EvalContext) -> None:
    actual = ctx.adapter.invoke(ctx.case.input)
    assert actual["label"] == ctx.case.expected["label"]
```

## Run it

Local:

```bash
uv run atal run --suite evals.sample:suite
uv run atal run --suite evals.sample:suite --min-accuracy 0.95
uv run atal check --run-id <run-id> --against <reference-run-id>
```

Remote:

```bash
docker compose up --build
uv run atal run --suite evals.sample:suite --remote --wait
```

Remote runs upload the suite bundle automatically. The Docker worker picks up queued runs, loads the bundle, runs the suite, and posts results back. If you are not using Docker, run `uv run atal worker` as a separate long-lived process on the self-hosted machine.

## CI examples

- GitHub Actions: `.github/workflows/Atalaia-ci-example.yml`
- GitLab CI: `.gitlab-ci.yml.example`

Both examples run the local suite and can optionally run a remote regression check when these variables are set:

- `ATALAIA_API_URL`
- `ATALAIA_TOKEN`
- `ATALAIA_PROJECT_SLUG`
- `ATALAIA_REFERENCE_RUN_ID`

## Public docs

Start at `docs/README.md` if you want a tiny docs index.
