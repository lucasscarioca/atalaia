# Quickstart

```bash
uv sync --dev
uv run oak-eval init
uv run oak-eval run --suite evals.sample:suite
```

Then edit `evals/sample.py` or add your own suite under `evals/`.

If you already have a self-hosted API running:

```bash
export OAK_EVAL_API_URL=...
export OAK_EVAL_TOKEN=...
uv run oak-eval worker
uv run oak-eval run --suite evals.sample:suite --remote --wait
uv run oak-eval check --run-id <run-id> --against <reference-run-id>
```

`<reference-run-id>` is a previous successful run ID from the API.
