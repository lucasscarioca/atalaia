# Quickstart

```bash
uv sync --dev
uv run oak-eval init
uv run oak-eval run --suite evals.sample:suite
```

Then edit `evals/sample.py` or add your own suite under `evals/`.

Remote/self-hosted loop:

```bash
docker compose up --build
```

This starts Postgres, the API, and the worker. In another terminal:

```bash
export OAK_EVAL_API_URL=http://localhost:8000
export OAK_EVAL_TOKEN=$(curl -s -X POST "$OAK_EVAL_API_URL/tokens" \
  -H "Content-Type: application/json" \
  -H "X-Oak-Eval-Admin-Token: ${OAK_EVAL_BOOTSTRAP_TOKEN:-dev-bootstrap}" \
  -d '{"name":"local-cli"}' | python -c 'import json,sys; print(json.load(sys.stdin)["token"])')
uv run oak-eval run --suite evals.sample:suite --remote --wait
uv run oak-eval check --run-id <run-id> --against <reference-run-id>
```

`<reference-run-id>` is a previous successful run ID from the API.

If you are not using Docker, run `uv run oak-eval worker` as a separate long-lived process on the self-hosted machine.
