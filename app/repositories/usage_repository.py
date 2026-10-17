from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.idempotency import IdempotencyRecord
from app.db.models.usage import UsageEvent, UsageType


class UsageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_idempotency(self, tenant_id: UUID, key: str) -> IdempotencyRecord | None:
        return self.session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == tenant_id,
                IdempotencyRecord.key == key,
            )
        ).scalar_one_or_none()

    def add_idempotency(self, record: IdempotencyRecord) -> None:
        self.session.add(record)

    def add_event(self, event: UsageEvent) -> None:
        self.session.add(event)

    def get_event_by_key(self, tenant_id: UUID, idempotency_key: str) -> UsageEvent | None:
        return self.session.execute(
            select(UsageEvent).where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()

    def sum_quantity(
        self,
        tenant_id: UUID,
        usage_type: UsageType,
        start: datetime,
        end: datetime,
    ) -> int:
        result = self.session.execute(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.usage_type == usage_type.value,
                UsageEvent.occurred_at >= start,
                UsageEvent.occurred_at < end,
            )
        ).scalar_one()
        return int(result)

    def sum_cost(self, tenant_id: UUID, start: datetime, end: datetime) -> int:
        result = self.session.execute(
            select(func.coalesce(func.sum(UsageEvent.cost_nano_usd), 0)).where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.occurred_at >= start,
                UsageEvent.occurred_at < end,
            )
        ).scalar_one()
        return int(result)

    def count_events(self, tenant_id: UUID) -> int:
        result = self.session.execute(
            select(func.count()).select_from(UsageEvent).where(UsageEvent.tenant_id == tenant_id)
        ).scalar_one()
        return int(result)
