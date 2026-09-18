"""API tests for app/routes.py.

Runs against the throwaway `anomaly_test` database via the `client` fixture
(TestClient + `get_session` dependency override).
"""

from tests.test_parsing import FIXTURE

FIXTURE_BYTES = FIXTURE.read_bytes()


def _upload(client, content: bytes = FIXTURE_BYTES, filename: str = "sample_nss_web.json"):
    return client.post(
        "/api/logs",
        files={"file": (filename, content, "application/json")},
    )


def test_upload_valid_file(client) -> None:
    response = _upload(client)
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "sample_nss_web.json"
    assert body["status"] == "completed"
    assert body["event_count"] == 6
    assert body["anomaly_count"] == 7
    assert isinstance(body["id"], int)


def test_upload_missing_file_field(client) -> None:
    assert client.post("/api/logs").status_code == 422


def test_upload_over_size_cap(client, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.MAX_UPLOAD_BYTES", 10)
    assert _upload(client).status_code == 413


def test_upload_unparseable_content(client) -> None:
    response = _upload(client, content=b"not json at all", filename="x.json")
    assert response.status_code == 422
    assert "detail" in response.json()


def test_upload_empty_file(client) -> None:
    assert _upload(client, content=b"", filename="x.json").status_code == 400


def test_upload_bad_extension(client) -> None:
    assert _upload(client, filename="x.exe").status_code == 400


def test_get_upload_status(client) -> None:
    upload_id = _upload(client).json()["id"]
    response = client.get(f"/api/uploads/{upload_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == upload_id
    assert body["status"] == "completed"
    assert body["event_count"] == 6
    assert body["anomaly_count"] == 7
    assert body["error_message"] is None


def test_get_upload_unknown(client) -> None:
    assert client.get("/api/uploads/999999").status_code == 404


def test_list_events_page(client) -> None:
    upload_id = _upload(client).json()["id"]
    response = client.get(
        f"/api/uploads/{upload_id}/events", params={"limit": 4, "offset": 0}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    assert body["limit"] == 4
    assert body["offset"] == 0
    assert len(body["items"]) == 4


def test_list_events_limit_is_capped(client) -> None:
    upload_id = _upload(client).json()["id"]
    body = client.get(
        f"/api/uploads/{upload_id}/events", params={"limit": 1000}
    ).json()
    assert body["limit"] == 200


def test_list_events_action_filter(client) -> None:
    upload_id = _upload(client).json()["id"]
    body = client.get(
        f"/api/uploads/{upload_id}/events", params={"action": "Block"}
    ).json()
    assert body["total"] == 2
    assert all(item["action"] == "Block" for item in body["items"])


def test_list_events_unknown_upload(client) -> None:
    assert client.get("/api/uploads/999999/events").status_code == 404


def test_summary_shape(client) -> None:
    upload_id = _upload(client).json()["id"]
    response = client.get(f"/api/uploads/{upload_id}/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["upload_id"] == upload_id
    assert body["total_events"] == 6
    assert body["unique_clients"] == 6
    assert body["unique_users"] == 5
    assert body["blocked_count"] == 2
    assert body["allowed_count"] == 4
    assert len(body["timeline"]) == 6
    rules = {anomaly["rule"] for anomaly in body["anomalies"]}
    assert {"threat-detected", "dlp-violation"} <= rules


def test_summary_unknown_upload(client) -> None:
    assert client.get("/api/uploads/999999/summary").status_code == 404
