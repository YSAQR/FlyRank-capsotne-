from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ValidationAppError
from app.db.models.idempotency import IdempotencyRecord
from app.db.models.plan import Plan
from app.db.models.usage import UsageType
from app.repositories.tenant_repository import TenantRepository
from app.repositories.usage_repository import UsageRepository
from app.schemas.generate import GenerateRequest, GenerateResponse
from app.services.metering_service import MeteringService
from app.services.pricing_service import PricingService, TokenUsage
from app.services.quota_service import QuotaService
from app.utils.hashing import canonical_hash
from app.utils.money import format_nano_usd


class UsageService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.tenants = TenantRepository(session)
        self.usage_repo = UsageRepository(session)
        self.metering = MeteringService(self.usage_repo)
        self.quota = QuotaService(self.usage_repo)
        self.pricing = PricingService()

    def generate(self, tenant_id: UUID, idempotency_key: str, body: GenerateRequest) -> GenerateResponse:
        if not idempotency_key or not idempotency_key.strip():
            raise ValidationAppError("Idempotency-Key header is required.")
        payload = body.model_dump()
        request_hash = canonical_hash(payload)

        subscription = self.tenants.get_subscription_for_update(tenant_id)
        existing = self.usage_repo.get_idempotency(tenant_id, idempotency_key)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise ConflictError(
                    "Idempotency key was reused with a different payload.",
                    {"idempotency_key": idempotency_key},
                )
            replay = dict(existing.response_body)
            replay["idempotent_replay"] = True
            return GenerateResponse.model_validate(replay)

        subscription = self.quota.require_billable_subscription(subscription)
        plan = self.session.get(Plan, subscription.plan_id)
        if plan is None:
            raise ValidationAppError("Subscription plan is missing.")

        tokens = body.billable_tokens()
        decision = self.quota.snapshot(tenant_id, subscription, plan)
        self.quota.assert_within_quota(decision, requested_api_calls=1, requested_tokens=tokens)

        token_usage = TokenUsage(
            fresh_input_tokens=body.input_tokens,
            cached_input_tokens=body.cached_input_tokens,
            output_tokens=body.output_tokens,
            reasoning_tokens=body.reasoning_tokens,
        )
        cost = self.pricing.quote(token_usage)
        generation_id = uuid4()

        self.metering.record(
            tenant_id=tenant_id,
            usage_type=UsageType.api_call,
            quantity=1,
            idempotency_key=f"{idempotency_key}:api_call",
            request_hash=request_hash,
            metadata={"generation_id": str(generation_id)},
        )
        self.metering.record(
            tenant_id=tenant_id,
            usage_type=UsageType.ai_tokens,
            quantity=tokens,
            idempotency_key=f"{idempotency_key}:ai_tokens",
            request_hash=request_hash,
            cost_nano_usd=cost,
            pricing_version=self.pricing.version,
            metadata={**body.token_breakdown(), "generation_id": str(generation_id)},
        )

        digest = hashlib.sha256(body.prompt.encode("utf-8")).hexdigest()[:12]
        response = GenerateResponse(
            generation_id=generation_id,
            output=(
                f"[demo generation {digest}] A reverse-proxy-style summary of your prompt "
                f"({len(body.prompt)} chars). No external model was called."
            ),
            usage={
                "api_calls": 1,
                **body.token_breakdown(),
                "billable_tokens": tokens,
            },
            cost={
                **format_nano_usd(cost),
                "pricing_version": self.pricing.version,
            },
            idempotent_replay=False,
            quota=decision.as_dict(extra_api=1, extra_tokens=tokens),
        )
        record = IdempotencyRecord(
            tenant_id=tenant_id,
            key=idempotency_key,
            request_hash=request_hash,
            status_code=200,
            response_body=response.model_dump(mode="json"),
        )
        self.usage_repo.add_idempotency(record)
        self.session.commit()
        return response

    def summary(self, tenant_id: UUID):
        from app.schemas.usage import UsageSummaryResponse

        subscription = self.tenants.get_subscription(tenant_id)
        if subscription is None:
            from app.core.exceptions import PaymentRequiredError

            raise PaymentRequiredError(
                "No subscription is attached to this tenant.",
                {"reason": "missing_subscription"},
            )
        plan = self.session.get(Plan, subscription.plan_id)
        if plan is None:
            raise ValidationAppError("Subscription plan is missing.")

        decision = self.quota.snapshot(tenant_id, subscription, plan)
        cost = self.usage_repo.sum_cost(tenant_id, decision.period_start, decision.period_end)
        policy = (
            "stripe_subscription_period"
            if subscription.current_period_start and subscription.current_period_end
            else "utc_calendar_month"
        )
        return UsageSummaryResponse(
            tenant_id=str(tenant_id),
            plan_code=plan.code,
            plan_name=plan.name,
            subscription_status=subscription.status,
            billing_period_start=decision.period_start,
            billing_period_end=decision.period_end,
            billing_period_policy=policy,
            api_calls=_metric(decision.api_used, decision.api_allowed),
            ai_tokens=_metric(decision.token_used, decision.token_allowed),
            cost={
                **format_nano_usd(cost),
                "pricing_version": self.pricing.version,
            },
            notes=(
                "Quantities (api_calls, ai_tokens) are usage metrics. "
                "cost is a monetary amount in nano-USD using the rate snapshot on each event."
            ),
        )


def _metric(used: int, allowed: int) -> dict:
    remaining = max(allowed - used, 0)
    percent = 0.0 if allowed == 0 else round((used / allowed) * 100, 4)
    return {"used": used, "allowed": allowed, "remaining": remaining, "percent_used": percent}
