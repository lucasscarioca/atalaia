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
docker compose up -d db
```

Optional: create a local `.env` if you want to override defaults:

```bash
cp .env.example .env
```

3. Run migrations:

```bash
uv run alembic upgrade head
```

4. Start API:

```bash
uv run uvicorn app.main:app --reload
```

5. Health/readiness checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Dockerized API

The API container applies migrations on startup, then starts Uvicorn:

```bash
docker compose up --build -d api
```

## Quick API examples

Create a dataset:

```bash
curl -X POST http://localhost:8000/datasets \
  -H 'Content-Type: application/json' \
  -d '{"name":"Support intents","task_type":"classification"}'
```

Import cases:

```bash
curl -X POST http://localhost:8000/datasets/<dataset_id>/cases:import \
  -H 'Content-Type: application/json' \
  -d '{"cases":[{"case_key":"intent-001","input":{"text":"I want to cancel"},"expected":{"label":"cancellation"}}]}'
```

Create a target:

```bash
curl -X POST http://localhost:8000/targets \
  -H 'Content-Type: application/json' \
  -d '{"name":"Classifier API","target_type":"http","base_url":"https://example.com","endpoint_path":"/classify"}'
```

Create a run:

```bash
curl -X POST http://localhost:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":"<dataset_id>","target_id":"<target_id>"}'
```
