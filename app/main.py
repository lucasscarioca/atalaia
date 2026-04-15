from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI

from app.api.routes.datasets import router as datasets_router
from app.api.routes.health import router as health_router
from app.api.routes.runs import router as runs_router
from app.api.routes.targets import router as targets_router
from app.core.logging import configure_logging

configure_logging()
logger = getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("agent eval api starting")
    yield


app = FastAPI(title="Agent Eval API", version="0.1.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(datasets_router)
app.include_router(targets_router)
app.include_router(runs_router)
