"""Business logic layer.

`parsing`   - raw NSS web-log bytes -> list[CanonicalEvent]
`detection` - events -> rule engine -> anomalies
`timeline`  - events + anomalies -> the summary the frontend renders

This package must not import FastAPI or SQLAlchemy: it is pure Python
operating on app/model shapes, which keeps it trivially unit-testable
(see tests/test_parsing.py and tests/test_detection.py).
"""
