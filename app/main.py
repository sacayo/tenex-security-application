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

Run locally from the repo root:
    uv run fastapi dev app/main.py
"""

from datetime import UTC, datetime
from fastapi import FastAPI
from app.routes import router as api_router
from contextlib import asynccontextmanager

    yield

app = FastAPI(
    title="Security Anomaly API",
    version="0.1.0",
    description="Web logs threat detection application for generating human-readable timeline of events and anomalies.",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Async context manager for the application."""

@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe (used by Docker healthchecks and manual smoke tests)."""
    return {"status": "healthy", "time": datetime.now(UTC).isoformat()}


app.include_router(api_router, prefix="/api")
