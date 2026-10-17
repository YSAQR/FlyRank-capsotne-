from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, ValidationAppError
from app.db.models.usage import UsageEvent, UsageType
from app.repositories.usage_repository import UsageRepository


class MeteringService:
    def __init__(self, usage_repo: UsageRepository) -> None:
        self.usage_repo = usage_repo

    def record(
        self,
        tenant_id: UUID,
        usage_type: UsageType,
        quantity: int,
        idempotency_key: str,
        request_hash: str,
        cost_nano_usd: int = 0,
        pricing_version: str | None = None,
        metadata: dict | None = None,
    ) -> UsageEvent:
        if quantity < 0:
            raise ValidationAppError("quantity must be a non-negative integer.")
        if not idempotency_key or len(idempotency_key) > 256:
            raise ValidationAppError("idempotency_key is required and must be at most 256 characters.")

        existing = self.usage_repo.get_event_by_key(tenant_id, idempotency_key)
        if existing is not None:
            return self._same_or_conflict(existing, usage_type, request_hash, idempotency_key)

        event = UsageEvent(
            tenant_id=tenant_id,
            usage_type=usage_type.value,
            quantity=quantity,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            cost_nano_usd=cost_nano_usd,
            pricing_version=pricing_version,
            request_metadata=metadata or {},
        )
        nested = self.usage_repo.session.begin_nested()
        self.usage_repo.add_event(event)
        try:
            self.usage_repo.session.flush()
            nested.commit()
        except IntegrityError:
            nested.rollback()
            raced = self.usage_repo.get_event_by_key(tenant_id, idempotency_key)
            if raced is None:
                raise
            return self._same_or_conflict(raced, usage_type, request_hash, idempotency_key)
        return event

    def _same_or_conflict(
        self,
        existing: UsageEvent,
        usage_type: UsageType,
        request_hash: str,
        idempotency_key: str,
    ) -> UsageEvent:
        if existing.request_hash != request_hash or existing.usage_type != usage_type.value:
            raise ConflictError(
                "Idempotency key was reused with a different payload.",
                {"idempotency_key": idempotency_key},
            )
        return existing
