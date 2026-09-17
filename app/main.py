"""Application entry point for the Security Anomaly API.

Layer map (see spec.md - "Architecture Overview"):
    app/main.py     -> you are here: app factory + wiring
    app/routes.py   -> HTTP layer (request/response handling)
    app/service/    -> business logic (parsing, detection, timeline)
    app/data/       -> persistence (engine, ORM tables, repository)
    app/model/      -> Pydantic schemas shared across all layers

"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.data import tables
from app.data.session import engine
from app.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the schema on startup (prototype only - no Alembic)."""
    tables.Base.metadata.create_all(bind=engine)
    yield


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


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe (used by Docker healthchecks and manual smoke tests)."""
    return {"status": "healthy", "time": datetime.now(UTC).isoformat()}


app.include_router(api_router, prefix="/api")
