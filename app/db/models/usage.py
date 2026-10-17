import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UsageType(StrEnum):
    api_call = "api_call"
    ai_tokens = "ai_tokens"


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_usage_events_tenant_idempotency"),
        Index("ix_usage_events_tenant_period_type", "tenant_id", "occurred_at", "usage_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    usage_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cost_nano_usd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    pricing_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    tenant = relationship("Tenant")
