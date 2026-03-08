from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.configs import router as configs_router
from app.api.routes.datasets import router as datasets_router
from app.api.routes.health import router as health_router
from app.api.routes.models import router as models_router
from app.api.routes.projects import router as projects_router
from app.api.routes.runs import router as runs_router
from app.api.routes.settings import router as settings_router
from app.api.websocket import connection_manager
from app.api.websocket.handler import router as ws_router
from app.core.config import settings
from app.core.database import create_tables
from app.services.settings_service import _load_persisted_overrides
from app.services.watchdog import recover_stale_runs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.projects_dir.mkdir(parents=True, exist_ok=True)
    await create_tables()
    _load_persisted_overrides()
    await recover_stale_runs()
    await connection_manager.start_resource_poller()
    yield
    await connection_manager.stop_resource_poller()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, tags=["health"])
app.include_router(projects_router)
app.include_router(configs_router)
app.include_router(models_router)
app.include_router(datasets_router)
app.include_router(settings_router)
app.include_router(runs_router)
app.include_router(ws_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
                "details": {},
            }
        },
    )
