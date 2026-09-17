"""Security Anomaly API - backend package.

Layer map: main.py (wiring) -> routes.py (HTTP) -> service/ (logic)
-> data/ (persistence), with model/ (Pydantic schemas) shared by all.
"""
