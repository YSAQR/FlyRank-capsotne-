"""Idempotent monthly usage reconciliation.

Reruns upsert the same aggregates and never increment historical charges.
Trigger: python -m app.jobs.monthly_usage_job
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.logging import configure_logging
from app.db.models.monthly_summary import MonthlyUsageSummary
from app.db.models.tenant import Tenant
from app.db.models.usage import UsageEvent, UsageType
from app.db.session import SessionLocal
from app.jobs.retry_utils import with_retries
from app.utils.period import utc_month_bounds

logger = logging.getLogger(__name__)


def reconcile_month(session: Session, period_start: datetime, period_end: datetime) -> int:
    tenants = session.execute(select(Tenant.id)).scalars().all()
    updated = 0
    for tenant_id in tenants:
        api_calls = int(
            session.execute(
                select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                    UsageEvent.tenant_id == tenant_id,
                    UsageEvent.usage_type == UsageType.api_call.value,
                    UsageEvent.occurred_at >= period_start,
                    UsageEvent.occurred_at < period_end,
                )
            ).scalar_one()
        )
        ai_tokens = int(
            session.execute(
                select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                    UsageEvent.tenant_id == tenant_id,
                    UsageEvent.usage_type == UsageType.ai_tokens.value,
                    UsageEvent.occurred_at >= period_start,
                    UsageEvent.occurred_at < period_end,
                )
            ).scalar_one()
        )
        cost = int(
            session.execute(
                select(func.coalesce(func.sum(UsageEvent.cost_nano_usd), 0)).where(
                    UsageEvent.tenant_id == tenant_id,
                    UsageEvent.occurred_at >= period_start,
                    UsageEvent.occurred_at < period_end,
                )
            ).scalar_one()
        )
        stmt = (
            pg_insert(MonthlyUsageSummary)
            .values(
                tenant_id=tenant_id,
                period_start=period_start,
                period_end=period_end,
                api_calls=api_calls,
                ai_tokens=ai_tokens,
                cost_nano_usd=cost,
            )
            .on_conflict_do_update(
                constraint="uq_monthly_usage_tenant_period",
                set_={
                    "period_end": period_end,
                    "api_calls": api_calls,
                    "ai_tokens": ai_tokens,
                    "cost_nano_usd": cost,
                },
            )
        )
        session.execute(stmt)
        updated += 1
    session.commit()
    logger.info(
        "monthly_usage_reconciled tenants=%s period_start=%s",
        updated,
        period_start.isoformat(),
    )
    return updated


def run() -> int:
    configure_logging()
    start, end = utc_month_bounds()

    def _job() -> int:
        session = SessionLocal()
        try:
            return reconcile_month(session, start, end)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return with_retries(_job, attempts=3, base_delay_seconds=0.5, operation_name="monthly_usage_reconcile")


def main() -> None:
    count = run()
    print(f"Reconciled {count} tenant(s) for the current UTC month.")


if __name__ == "__main__":
    main()
