# Quickstart

```bash
uv sync --dev
uv run atal init
uv run atal run --suite evals.sample:suite
```

Then edit `evals/sample.py` or add your own suite under `evals/`.

Remote/self-hosted loop:

```bash
docker compose up --build
```

This starts Postgres, the API, and the worker. In another terminal:

```bash
export ATALAIA_API_URL=http://localhost:8000
export ATALAIA_TOKEN=$(curl -s -X POST "$ATALAIA_API_URL/tokens" \
  -H "Content-Type: application/json" \
  -H "X-Atalaia-Admin-Token: ${ATALAIA_BOOTSTRAP_TOKEN:-dev-bootstrap}" \
  -d '{"name":"local-cli"}' | python -c 'import json,sys; print(json.load(sys.stdin)["token"])')
uv run atal run --suite evals.sample:suite --remote --wait
uv run atal check --run-id <run-id> --against <reference-run-id>
```

`<reference-run-id>` is a previous successful run ID from the API.

If you are not using Docker, run `uv run atal worker` as a separate long-lived process on the self-hosted machine.
