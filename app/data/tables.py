"""SQLAlchemy ORM models: the database schema.

Four tables (columns + rationale in spec.md - "Data Model"):

    uploads     - one row per uploaded file (metadata + processing status)
    events      - one row per normalized log line (FK -> uploads)
    anomalies   - one row per detected anomaly (FK -> uploads, optional FK -> events)
    narratives  - at most one cached LLM brief per upload (FK -> uploads, unique)
"""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    events: Mapped[list["Event"]] = relationship(
        back_populates="upload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    anomalies: Mapped[list["Anomaly"]] = relationship(
        back_populates="upload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    narrative: Mapped["Narrative | None"] = relationship(
        back_populates="upload",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_upload_id_timestamp", "upload_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    client_ip: Mapped[str] = mapped_column(String(45))
    username: Mapped[str | None] = mapped_column(String(255), default=None)
    method: Mapped[str | None] = mapped_column(String(16), default=None)
    url: Mapped[str] = mapped_column(Text)
    host: Mapped[str | None] = mapped_column(String(255), default=None)
    status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    action: Mapped[str] = mapped_column(String(16))
    url_category: Mapped[str | None] = mapped_column(String(100), default=None)
    threat_name: Mapped[str | None] = mapped_column(String(255), default=None)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    bytes_sent: Mapped[int] = mapped_column(BigInteger, default=0)
    bytes_received: Mapped[int] = mapped_column(BigInteger, default=0)
    user_agent: Mapped[str | None] = mapped_column(Text, default=None)
    dlp_dictionary: Mapped[str | None] = mapped_column(String(255), default=None)
    raw: Mapped[dict] = mapped_column(JSONB)

    upload: Mapped["Upload"] = relationship(back_populates="events")
    anomalies: Mapped[list["Anomaly"]] = relationship(back_populates="event")


class Anomaly(Base):
    __tablename__ = "anomalies"
    __table_args__ = (Index("ix_anomalies_upload_id", "upload_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"))
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), default=None
    )
    rule: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    upload: Mapped["Upload"] = relationship(back_populates="anomalies")
    event: Mapped["Event | None"] = relationship(back_populates="anomalies")


class Narrative(Base):
    """Cached LLM brief. One row per upload; regenerations overwrite it.

    `status` is "pending" while a background task is running, then "ready"
    or "failed". `(model, prompt_version)` records what produced `content`
    so a prompt change can invalidate the cache without a migration.
    """

    __tablename__ = "narratives"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(
        ForeignKey("uploads.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending")
    model: Mapped[str | None] = mapped_column(String(255), default=None)
    prompt_version: Mapped[str | None] = mapped_column(String(64), default=None)
    risk_level: Mapped[str] = mapped_column(String(16), default="none")
    content: Mapped[dict | None] = mapped_column(JSONB, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    latency_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    upload: Mapped["Upload"] = relationship(back_populates="narrative")
