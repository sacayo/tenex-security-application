"""Pure business logic.

``parsing``   - raw NSS bytes -> list[CanonicalEvent].
``detection`` - events -> rule engine -> anomalies.
``timeline``  - events and anomalies -> the rendered summary.
``narrative`` - facts block, prompt, and output validation.

This package imports no FastAPI, SQLAlchemy, or httpx, which keeps it
unit-testable without external services.
"""
