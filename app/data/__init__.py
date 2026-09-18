"""Database layer.

``session``    - engine and session factory (the only reader of DATABASE_URL).
``tables``     - SQLAlchemy ORM models.
``repository`` - every read and write; routes call these, never raw SQL.

Nothing outside this package may import SQLAlchemy.
"""
