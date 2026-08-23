from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.config import get_settings
from app.routes.driving_event import router as driving_event_router
from app.routes.driving_session import router as driving_session_router
from app.routes.health import router as health_router
from app.routes.master_config import router as master_config_router
from app.routes.operational_exception import router as operational_exception_router
from app.routes.s3_upload import router as s3_upload_router
from app.routes.trip_segment import router as trip_segment_router
from db import database as db_mod
from db.database import init_engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    init_engine(settings.database_url)
    yield
    if db_mod._engine is not None:
        db_mod._engine.dispose()
        db_mod._engine = None


def create_app() -> FastAPI:
    application = FastAPI(title="NetraPi ingest", lifespan=lifespan)
    application.include_router(health_router)
    application.include_router(master_config_router)
    application.include_router(driving_session_router)
    application.include_router(trip_segment_router)
    application.include_router(driving_event_router)
    application.include_router(operational_exception_router)
    application.include_router(s3_upload_router)
    return application


app = create_app()
