"""Smoke test: the app imports and the liveness probe answers.

This one already passes - it guards the wiring in app/main.py while you
build out the rest.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
