"""API tests for app/routes.py - write these last, once the layers below work.

Suggested cases (see spec.md - "Testing Strategy"):

    POST /api/logs
      - valid file -> 201 with UploadResponse (id, counts)
      - no file / wrong form field -> 422 (FastAPI gives you this for free)
      - file over the size cap -> 413
      - unparseable content -> 422 with a useful detail message
      - empty file -> 400

    GET /api/uploads/{id}
      - existing upload -> 200 with status metadata
      - unknown id -> 404

    GET /api/uploads/{id}/events
      - returns a page with total/limit/offset
      - respects limit cap; filters (action, url_category) narrow results

    GET /api/uploads/{id}/summary
      - returns timeline buckets + anomalies for a known upload
      - unknown id -> 404

Use fastapi.testclient.TestClient (see tests/test_health.py). Point the app
at a throwaway database for these tests - e.g. override the get_session
dependency (TestClient + app.dependency_overrides) or set DATABASE_URL to a
test database in a fixture.
"""
