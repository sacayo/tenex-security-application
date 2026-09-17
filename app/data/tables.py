"""SQLAlchemy ORM models: the database schema.

Three tables (full column lists + rationale in spec.md - "Data Model"):

    uploads    - one row per uploaded file (metadata + processing status)
    events     - one row per normalized log line (FK -> uploads)
    anomalies  - one row per detected anomaly (FK -> uploads, optional FK -> events)

TODO:
    1. Declare a Declarative Base.
    2. Define the three ORM classes following the ER diagram in spec.md.
       Remember: ForeignKey("uploads.id", ondelete="CASCADE") on both child
       tables, an index on events(upload_id, timestamp), and store the raw
       NSS record on events as JSONB for later debugging.
    3. Keep ORM models in this file ONLY - API shapes belong in app/model/.
"""
