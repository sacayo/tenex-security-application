"""Pydantic model definitions shared across all layers.

`event`   - the canonical normalized event + its API representation.
`upload`  - upload metadata/status shapes.
`summary` - timeline buckets, anomalies, and the summary response.

Everything here is plain data + validation. No logic beyond simple
validators belongs in this package.
"""
