from datetime import datetime

from app.core.exceptions import PaymentRequiredError, QuotaExceededError
from app.db.models.plan import Plan
from app.db.models.subscription import PAYMENT_REQUIRED_STATUSES, Subscription
from app.db.models.usage import UsageType
from app.repositories.usage_repository import UsageRepository
from app.utils.period import billing_period, seconds_until


class QuotaDecision:
    def __init__(
        self,
        api_used: int,
        token_used: int,
        api_allowed: int,
        token_allowed: int,
        period_start: datetime,
        period_end: datetime,
    ) -> None:
        self.api_used = api_used
        self.token_used = token_used
        self.api_allowed = api_allowed
        self.token_allowed = token_allowed
        self.period_start = period_start
        self.period_end = period_end

    def as_dict(self, extra_api: int = 0, extra_tokens: int = 0) -> dict:
        api_used = self.api_used + extra_api
        token_used = self.token_used + extra_tokens
        return {
            "api_calls_used": api_used,
            "api_calls_allowed": self.api_allowed,
            "ai_tokens_used": token_used,
            "ai_tokens_allowed": self.token_allowed,
            "billing_period_start": self.period_start.isoformat(),
            "billing_period_end": self.period_end.isoformat(),
        }


class QuotaService:
    def __init__(self, usage_repo: UsageRepository) -> None:
        self.usage_repo = usage_repo

    def require_billable_subscription(self, subscription: Subscription | None) -> Subscription:
        if subscription is None:
            raise PaymentRequiredError(
                "No subscription is attached to this tenant.",
                {"reason": "missing_subscription"},
            )
        if subscription.status in PAYMENT_REQUIRED_STATUSES or not subscription.is_billable:
            raise PaymentRequiredError(
                "Subscription is not in a billable state. Upgrade or complete payment to continue.",
                {"reason": "subscription_not_billable", "status": subscription.status},
            )
        return subscription

    def snapshot(self, tenant_id, subscription: Subscription, plan: Plan) -> QuotaDecision:
        start, end = billing_period(subscription)
        api_used = self.usage_repo.sum_quantity(tenant_id, UsageType.api_call, start, end)
        token_used = self.usage_repo.sum_quantity(tenant_id, UsageType.ai_tokens, start, end)
        return QuotaDecision(
            api_used=api_used,
            token_used=token_used,
            api_allowed=plan.monthly_api_call_quota,
            token_allowed=plan.monthly_ai_token_quota,
            period_start=start,
            period_end=end,
        )

    def assert_within_quota(
        self,
        decision: QuotaDecision,
        requested_api_calls: int,
        requested_tokens: int,
    ) -> None:
        retry_after = seconds_until(decision.period_end)
        if requested_api_calls > decision.api_allowed or requested_tokens > decision.token_allowed:
            raise QuotaExceededError(
                "Requested quantity exceeds the plan quota by itself.",
                {
                    **decision.as_dict(),
                    "requested_api_calls": requested_api_calls,
                    "requested_tokens": requested_tokens,
                },
                retry_after=retry_after,
            )
        if decision.api_used + requested_api_calls > decision.api_allowed:
            raise QuotaExceededError(
                "API call quota would be exceeded.",
                {
                    **decision.as_dict(),
                    "requested_api_calls": requested_api_calls,
                    "metric": "api_call",
                },
                retry_after=retry_after,
            )
        if decision.token_used + requested_tokens > decision.token_allowed:
            raise QuotaExceededError(
                "AI token quota would be exceeded.",
                {
                    **decision.as_dict(),
                    "requested_tokens": requested_tokens,
                    "metric": "ai_tokens",
                },
                retry_after=retry_after,
            )
