"""Engine + session factory.

This module is the ONLY place that knows how to connect to the database.
Read the connection string from the environment so the same code runs on
your laptop and inside Docker Compose (spec.md - "Docker & Deployment").

Prereq: add the dependencies yourself -
    uv add sqlalchemy "psycopg[binary]"

TODO(spec.md - "Data Model"):
    1. Read DATABASE_URL from the environment, e.g.
       postgresql+psycopg://postgres:postgres@localhost:5432/anomaly
    2. Create the module-level engine: engine = create_engine(DATABASE_URL)
    3. Create a session factory: SessionLocal = sessionmaker(bind=engine, ...)
    4. Write a FastAPI dependency that yields a session and always closes it:

           def get_session() -> Iterator[Session]:
               ...

       Routes then declare `session: Session = Depends(get_session)`.
    5. (First run) create the schema - either Base.metadata.create_all(engine)
       on startup, or a small init script. Your choice; document it in spec.md.
"""
