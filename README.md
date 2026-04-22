# oak-eval

Git-native, self-hosted evaluation system for AI agents.

## What this is

oak-eval is pivoting toward an evals-as-code workflow where suites live in the repo, runs can execute locally or on a self-hosted server, and CI can gate releases using reproducible evaluation results.

## Stack

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy
- Alembic
- PostgreSQL
- uv

## Current status

The repo is being reshaped around the new oak-eval direction.

## Try the local SDK

```bash
uv run oak-eval init
uv run oak-eval run --suite evals.sample:suite
uv run oak-eval run --suite evals.sample:suite --min-accuracy 0.95
uv run oak-eval run --suite evals.sample:suite --remote --wait
uv run oak-eval check --run-id <run-id> --against <reference-run-id>
uv run oak-eval worker
```

Or use the Python SDK directly from `oak_eval` and author suites under `evals/`.

The SDK also includes `oak_eval.adapters.http.HTTPAdapter` for suites that check a live HTTP service.

## Remote API foundation

- Create a token with `POST /auth/tokens` using `X-Oak-Eval-Admin-Token`
- Use `Authorization: Bearer <token>` for `/projects` and `/runs`
- Remote runs upload a zipped suite bundle automatically, and workers poll queued runs and complete them through the API
