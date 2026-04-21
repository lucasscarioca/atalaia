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
```

Or use the Python SDK directly from `oak_eval` and author suites under `evals/`.
