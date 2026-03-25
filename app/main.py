from fastapi import FastAPI

from app.api.routes.datasets import router as datasets_router
from app.api.routes.runs import router as runs_router
from app.api.routes.targets import router as targets_router

app = FastAPI(title="Agent Eval API", version="0.1.0")

app.include_router(datasets_router)
app.include_router(targets_router)
app.include_router(runs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
