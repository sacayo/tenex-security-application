"""Database storage/interface layer.

`session`    - engine + session factory (the only place that knows DATABASE_URL).
`tables`     - SQLAlchemy ORM models (the database schema).
`repository` - all persist/query functions; routes call these, never raw SQL.

Nothing outside this package may import sqlalchemy.
"""
