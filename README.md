# Agent Eval

API-first evaluation suite for LLM tasks and agent systems.

## Stack

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy
- Alembic
- PostgreSQL
- uv

## Local Setup

1. Install dependencies:

```bash
uv sync
```

2. Start PostgreSQL in Docker:

```bash
cp .env.example .env
docker compose up -d db
```

3. Run migrations:

```bash
uv run alembic upgrade head
```

4. Start API:

```bash
uv run uvicorn app.main:app --reload
```

5. Health check:

```bash
curl http://localhost:8000/health
```
