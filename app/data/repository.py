"""Repository: every database read/write the rest of the app needs.

Routes call these functions; they never write SQL themselves. Keeping all
queries here means there is exactly one place to audit for injection risks
and exactly one place to add indexes/caching later.

TODO(spec.md - "Data Model"): implement, roughly in this order.
Suggested signatures:

    def create_upload(session, *, filename: str, file_size: int) -> Upload
        # Insert an uploads row with status "parsing" and return it.

    def mark_upload_completed(session, upload_id, event_count, anomaly_count) -> None
        # Set status "completed", counts, and processed_at.

    def mark_upload_failed(session, upload_id, error_message) -> None
        # Set status "failed" + error_message (call from the route's except path).

    def insert_events(session, upload_id, events: list[CanonicalEvent]) -> None
        # Bulk-insert normalized events (session.add_all / bulk_save_objects).

    def insert_anomalies(session, upload_id, anomalies: list[DetectedAnomaly],
                         event_ids: list[int]) -> None
        # Persist anomalies; map event_index -> the real events.id.

    def get_upload(session, upload_id: int) -> Upload | None

    def list_events(session, upload_id, *, limit, offset,
                    action=None, url_category=None, anomalies_only=False)
            # Return (page, total) for the events endpoint.

    def get_events_for_summary(session, upload_id) -> list[Event]
    def get_anomalies(session, upload_id) -> list[Anomaly]

All queries must go through the ORM (select() / session.query) - never
string-formatted SQL.
"""
