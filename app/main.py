from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.api.routes.runs import router as runs_router
from app.core.logging import configure_logging

configure_logging()
logger = getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("oak-eval app starting")
    yield


app = FastAPI(title="oak-eval", version="0.1.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(runs_router)
