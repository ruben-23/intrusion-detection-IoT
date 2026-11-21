"""Modele SQLAlchemy (async). Implicit SQLite local; PostgreSQL prin DATABASE_URL, ex:
postgresql+asyncpg://user:pass@localhost:5432/ids
"""
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, BigInteger, DateTime, Float, ForeignKey, Integer,
                        String, Uuid)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ids.db")
engine = create_async_engine(DATABASE_URL)
Session = async_sessionmaker(engine, expire_on_commit=False)

JsonType = JSON().with_variant(JSONB(), "postgresql")   # JSONB pe Postgres
PkType = BigInteger().with_variant(Integer(), "sqlite")  # autoincrement în SQLite
TS = DateTime(timezone=True)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Gateway(Base):
    __tablename__ = "gateways"
    gateway_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    cpu_usage_pct: Mapped[float | None] = mapped_column(Float)
    ram_mb_used: Mapped[float | None] = mapped_column(Float)
    avg_inference_ms: Mapped[float | None] = mapped_column(Float)
    last_heartbeat: Mapped[datetime] = mapped_column(TS, default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="ONLINE")


class Device(Base):
    __tablename__ = "devices"
    mac_address: Mapped[str] = mapped_column(String(17), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    gateway_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("gateways.gateway_id", ondelete="CASCADE"))
    device_type: Mapped[str | None] = mapped_column(String(50))
    current_status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    registered_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Telemetry(Base):
    __tablename__ = "telemetry"
    id: Mapped[int] = mapped_column(PkType, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(TS, nullable=False, index=True)
    mac_address: Mapped[str] = mapped_column(
        String(17), ForeignKey("devices.mac_address", ondelete="CASCADE"), index=True)
    total_packets: Mapped[int] = mapped_column(Integer, nullable=False)
    total_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    active_flows: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class Incident(Base):
    __tablename__ = "incidents"
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(TS, nullable=False, index=True)
    mac_address: Mapped[str] = mapped_column(
        String(17), ForeignKey("devices.mac_address", ondelete="CASCADE"))
    predicted_class: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    action_taken: Mapped[str] = mapped_column(String(50), nullable=False)
    inference_latency_ms: Mapped[float | None] = mapped_column(Float)
    forensic_features: Mapped[dict] = mapped_column(JsonType, nullable=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
