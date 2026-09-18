"""Pydantic schemas shared by every layer.

``event``     - canonical event and its API representation.
``upload``    - upload metadata and status shapes.
``summary``   - timeline buckets, anomalies, and the summary response.
``narrative`` - the model-written brief.

Plain data and validation only; no business logic.
"""
