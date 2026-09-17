"""HTTP layer: the REST API surface.

Each handler should stay *thin*: validate input -> call into `app.service`
-> return shapes defined in `app.model`. No parsing, detection, or SQL in
this file.

Implement the endpoints below in this order (spec.md - "Build Order"):
    1. upload_log       (the core of the whole app)
    2. get_upload
    3. get_summary
    4. list_events

The exact request/response contract, example payloads, and error codes are
specified in spec.md - "API Contract". The frontend in `web/` is built
against that contract, so do not deviate from it without updating both
spec.md and `web/lib/api.ts`.
"""

from fastapi import APIRouter, UploadFile

from app.model.event import EventPage
from app.model.summary import SummaryResponse
from app.model.upload import UploadResponse, UploadStatus

router = APIRouter()


@router.post("/logs", status_code=201)
async def upload_log(file: UploadFile) -> UploadResponse:
    """Accept an NSS web-log file, parse it, run detection, persist everything.

    TODO(spec.md - "API Contract" -> POST /api/logs):
      1. Validate the upload: size cap and extension (reject early with
         413 / 400 respectively).
      2. Read the bytes and call app.service.parsing.parse_nss_feed.
      3. Call app.service.detection.run_rules on the parsed events.
      4. Persist upload + events + anomalies via app.data.repository.
      5. Return UploadResponse with the new upload id and counts.
    """
    raise NotImplementedError("TODO: implement POST /api/logs (see spec.md)")


@router.get("/uploads/{upload_id}")
def get_upload(upload_id: int) -> UploadStatus:
    """Return metadata/processing status for one upload.

    TODO: look up the upload via app.data.repository; 404 if it does not
    exist.
    """
    raise NotImplementedError("TODO: implement GET /api/uploads/{id}")


@router.get("/uploads/{upload_id}/events")
def list_events(upload_id: int, limit: int = 50, offset: int = 0) -> EventPage:
    """Return a page of normalized events for one upload.

    TODO: enforce a max `limit` (e.g. 200), support the optional filters
    from spec.md (`action`, `url_category`, `anomalies_only`), and 404 for
    unknown uploads.
    """
    raise NotImplementedError("TODO: implement GET /api/uploads/{id}/events")


@router.get("/uploads/{upload_id}/summary")
def get_summary(upload_id: int) -> SummaryResponse:
    """Return the human-readable summary + timeline the frontend renders.

    TODO: load events + anomalies via the repository, then delegate to
    app.service.timeline.build_summary.
    """
    raise NotImplementedError("TODO: implement GET /api/uploads/{id}/summary")
