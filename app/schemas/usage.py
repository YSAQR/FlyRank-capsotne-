from datetime import datetime

from pydantic import BaseModel

from app.schemas.generate import CostBreakdown


class QuotaMetric(BaseModel):
    used: int
    allowed: int
    remaining: int
    percent_used: float


class UsageSummaryResponse(BaseModel):
    tenant_id: str
    plan_code: str
    plan_name: str
    subscription_status: str
    billing_period_start: datetime
    billing_period_end: datetime
    billing_period_policy: str
    api_calls: QuotaMetric
    ai_tokens: QuotaMetric
    cost: CostBreakdown
    notes: str
