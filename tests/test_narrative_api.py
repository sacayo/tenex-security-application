"""API tests for the narrative endpoints in app/routes.py.

Uses the `client` fixture (throwaway `anomaly_test` database) and overrides
the `get_llm_client` dependency with an in-memory fake, so nothing here ever
reaches a model server. TestClient runs BackgroundTasks synchronously
before returning, so a POST that schedules generation is followed
immediately by a GET that sees the terminal state.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.config import Settings
from app.data import repository
from app.llm.client import LlmCompletion, LlmUnavailable, get_llm_client
from app.main import app
from app.service.narrative import PROMPT_VERSION
from tests.test_parsing import FIXTURE

FIXTURE_BYTES = FIXTURE.read_bytes()

GROUNDED: dict[str, Any] = {
    "headline": "Seven anomalies were flagged across six events.",
    "overview": "The logs show a short burst of activity with one blocked threat.",
    "key_findings": ["A known threat was blocked.", "A DLP violation was recorded."],
    "recommended_actions": ["Review the affected client.", "Confirm the DLP policy."],
}


class FakeClient:
    model = "fake-model"

    def __init__(
        self, data: dict[str, Any] | None = None, error: Exception | None = None
    ):
        self.data = data or GROUNDED
        self.error = error
        self.calls = 0
        self.last_prompt = ""

    def complete(
        self, *, system_prompt: str, user_prompt: str, json_schema: dict
    ) -> LlmCompletion:
        self.calls += 1
        self.last_prompt = user_prompt
        if self.error is not None:
            raise self.error
        return LlmCompletion(data=self.data, model=self.model, latency_ms=7)


@pytest.fixture
def fake_llm(client) -> FakeClient:
    fake = FakeClient()
    app.dependency_overrides[get_llm_client] = lambda: fake
    return fake


def _upload(client) -> int:
    response = client.post(
        "/api/logs",
        files={"file": ("sample_nss_web.json", FIXTURE_BYTES, "application/json")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _url(upload_id: int, **params) -> str:
    query = "&".join(f"{k}={str(v).lower()}" for k, v in params.items())
    return f"/api/uploads/{upload_id}/narrative" + (f"?{query}" if query else "")


# --- guards -----------------------------------------------------------------


def test_post_unknown_upload_is_404(client, fake_llm) -> None:
    assert client.post(_url(999999)).status_code == 404


def test_get_unknown_upload_is_404(client) -> None:
    assert client.get(_url(999999)).status_code == 404


def test_post_when_llm_disabled_is_503(client) -> None:
    app.dependency_overrides[get_llm_client] = lambda: None
    upload_id = _upload(client)
    response = client.post(_url(upload_id))
    assert response.status_code == 503
    assert "not enabled" in response.json()["detail"]


def test_post_on_incomplete_upload_is_409(client, session, fake_llm) -> None:
    upload = repository.create_upload(session, filename="x.json", file_size=1)
    assert client.post(_url(upload.id)).status_code == 409
    assert fake_llm.calls == 0


def test_get_before_any_request_is_404(client) -> None:
    upload_id = _upload(client)
    response = client.get(_url(upload_id))
    assert response.status_code == 404
    assert "not requested" in response.json()["detail"]


# --- happy path + cache -----------------------------------------------------


def test_post_schedules_then_get_is_ready(client, fake_llm) -> None:
    upload_id = _upload(client)

    response = client.post(_url(upload_id))
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["sections"] is None

    # Background task has run by the time POST returned.
    assert fake_llm.calls == 1
    assert "FACTS" in fake_llm.last_prompt
    assert "Total events: 6" in fake_llm.last_prompt

    ready = client.get(_url(upload_id))
    assert ready.status_code == 200
    body = ready.json()
    assert body["status"] == "ready"
    assert body["risk_level"] == "high"
    assert body["model"] == "fake-model"
    assert body["prompt_version"] == PROMPT_VERSION
    assert body["generated_at"] is not None
    assert body["sections"]["headline"] == GROUNDED["headline"]
    assert body["sections"]["key_findings"] == GROUNDED["key_findings"]


def test_second_post_serves_cache_without_calling_model(client, fake_llm) -> None:
    upload_id = _upload(client)
    client.post(_url(upload_id))
    response = client.post(_url(upload_id))
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert fake_llm.calls == 1


def test_post_while_pending_schedules_nothing(client, session, fake_llm) -> None:
    upload_id = _upload(client)
    repository.mark_narrative_pending(session, upload_id)

    response = client.post(_url(upload_id))
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    assert fake_llm.calls == 0


def test_stale_prompt_version_triggers_regeneration(client, session, fake_llm) -> None:
    upload_id = _upload(client)
    client.post(_url(upload_id))
    row = repository.get_narrative(session, upload_id)
    row.prompt_version = "ancient"
    session.commit()

    response = client.post(_url(upload_id))
    assert response.status_code == 202
    assert fake_llm.calls == 2


# --- stuck pending recovery -------------------------------------------------


def _age_row(session, upload_id: int, seconds: int) -> None:
    row = repository.get_narrative(session, upload_id)
    row.updated_at = datetime.now(UTC) - timedelta(seconds=seconds)
    session.commit()


def test_get_flips_stuck_pending_to_failed(client, session, fake_llm) -> None:
    upload_id = _upload(client)
    repository.mark_narrative_pending(session, upload_id)
    _age_row(session, upload_id, seconds=10_000)

    body = client.get(_url(upload_id)).json()
    assert body["status"] == "failed"
    assert "timed out" in body["error_message"]


def test_post_regenerates_stuck_pending(client, session, fake_llm) -> None:
    upload_id = _upload(client)
    repository.mark_narrative_pending(session, upload_id)
    _age_row(session, upload_id, seconds=10_000)

    assert client.post(_url(upload_id)).status_code == 202
    assert fake_llm.calls == 1
    assert client.get(_url(upload_id)).json()["status"] == "ready"


# --- refresh + cooldown -----------------------------------------------------


def test_refresh_inside_cooldown_is_429(client, fake_llm) -> None:
    upload_id = _upload(client)
    client.post(_url(upload_id))
    response = client.post(_url(upload_id, refresh=True))
    assert response.status_code == 429
    assert fake_llm.calls == 1


def test_refresh_after_cooldown_regenerates(client, fake_llm, monkeypatch) -> None:
    upload_id = _upload(client)
    client.post(_url(upload_id))
    monkeypatch.setattr(
        "app.routes.get_settings", lambda: Settings(llm_refresh_cooldown_seconds=0)
    )
    response = client.post(_url(upload_id, refresh=True))
    assert response.status_code == 202
    assert fake_llm.calls == 2
    assert client.get(_url(upload_id)).json()["status"] == "ready"


# --- failure paths ----------------------------------------------------------


def test_model_failure_is_recorded_and_not_retried_on_plain_post(
    client, fake_llm
) -> None:
    fake_llm.error = LlmUnavailable("model did not respond within the timeout")
    upload_id = _upload(client)

    assert client.post(_url(upload_id)).status_code == 202
    body = client.get(_url(upload_id)).json()
    assert body["status"] == "failed"
    assert "timeout" in body["error_message"]
    assert body["sections"] is None
    assert body["risk_level"] == "high"  # still computed deterministically

    # A plain reload does not hammer a down model; Retry uses refresh=true.
    again = client.post(_url(upload_id))
    assert again.status_code == 200
    assert again.json()["status"] == "failed"
    assert fake_llm.calls == 1


def test_ungrounded_output_is_rejected(client, fake_llm) -> None:
    fake_llm.data = {**GROUNDED, "overview": "Traffic to evil.example.com was seen."}
    upload_id = _upload(client)
    client.post(_url(upload_id))
    body = client.get(_url(upload_id)).json()
    assert body["status"] == "failed"
    assert "ungrounded" in body["error_message"]
    assert "evil.example.com" in body["error_message"]


def test_unexpected_exception_never_propagates(client, fake_llm) -> None:
    fake_llm.error = RuntimeError("boom")
    upload_id = _upload(client)
    assert client.post(_url(upload_id)).status_code == 202
    body = client.get(_url(upload_id)).json()
    assert body["status"] == "failed"
    assert "Unexpected error" in body["error_message"]


# --- zero-event upload ------------------------------------------------------


def test_zero_event_upload_gets_canned_brief_without_model_call(
    client, session, fake_llm
) -> None:
    upload = repository.create_upload(session, filename="empty.json", file_size=2)
    repository.mark_upload_completed(session, upload.id, event_count=0, anomaly_count=0)

    assert client.post(_url(upload.id)).status_code == 202
    body = client.get(_url(upload.id)).json()
    assert body["status"] == "ready"
    assert body["model"] == "none"
    assert body["risk_level"] == "none"
    assert "No web-log events" in body["sections"]["headline"]
    assert fake_llm.calls == 0

    # Cached on the next POST as well.
    assert client.post(_url(upload.id)).status_code == 200
    assert fake_llm.calls == 0
