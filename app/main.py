"""Application entry point for the Security Anomaly API.

This module only *wires things together*: it creates the FastAPI app,
exposes the liveness probe, and mounts the HTTP routers from
`app.routes`. It should contain no business logic.

Layer map (see spec.md - "Architecture Overview"):
    app/main.py     -> you are here: app factory + wiring
    app/routes.py   -> HTTP layer (request/response handling)
    app/service/    -> business logic (parsing, detection, timeline)
    app/data/       -> persistence (engine, ORM tables, repository)
    app/model/      -> Pydantic schemas shared across all layers

"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.data import tables
from app.data.session import engine, log_engine_target
from app.log_config import (
    configure_logging,
    reset_request_id,
    set_request_id,
)
from app.routes import router as api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure logging and create the schema on startup."""
    configure_logging()
    log_engine_target()
    tables.Base.metadata.create_all(bind=engine)
    logger.info("schema ready")
    yield
    logger.info("shutdown complete")


app = FastAPI(
    title="Security Anomaly API",
    version="0.1.0",
    description="Web logs threat detection application for generating human-readable timeline of events and anomalies.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = set_request_id()
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "unhandled error method=%s path=%s",
            request.method,
            request.url.path,
        )
        raise
    else:
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %d %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
    finally:
        reset_request_id()


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe (used by Docker healthchecks and manual smoke tests)."""
    return {"status": "healthy", "time": datetime.now(UTC).isoformat()}


app.include_router(api_router, prefix="/api")
