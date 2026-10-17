"""Idempotent seed for plans, a demo tenant, and a Free subscription."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.plan import Plan
from app.db.models.subscription import Subscription
from app.db.models.tenant import Tenant, TenantStatus
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

DEMO_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DEMO_TENANT_NAME = "FlyRank Demo Tenant"
FREE_PLAN_CODE = "free"
PRO_PLAN_CODE = "pro"


def seed_plans(session: Session) -> dict[str, Plan]:
    settings = get_settings()
    specs = [
        (FREE_PLAN_CODE, "Free", settings.free_api_call_quota, settings.free_ai_token_quota),
        (PRO_PLAN_CODE, "Pro", settings.pro_api_call_quota, settings.pro_ai_token_quota),
    ]
    plans: dict[str, Plan] = {}
    for code, name, api_quota, token_quota in specs:
        plan = session.execute(select(Plan).where(Plan.code == code)).scalar_one_or_none()
        if plan is None:
            plan = Plan(
                code=code,
                name=name,
                monthly_api_call_quota=api_quota,
                monthly_ai_token_quota=token_quota,
            )
            session.add(plan)
            session.flush()
        else:
            plan.name = name
            plan.monthly_api_call_quota = api_quota
            plan.monthly_ai_token_quota = token_quota
        plans[code] = plan
    return plans


def seed_demo_tenant(session: Session, free_plan: Plan) -> Tenant:
    tenant = session.get(Tenant, DEMO_TENANT_ID)
    if tenant is None:
        tenant = Tenant(id=DEMO_TENANT_ID, name=DEMO_TENANT_NAME, status=TenantStatus.active.value)
        session.add(tenant)
        session.flush()
    else:
        tenant.name = DEMO_TENANT_NAME
        tenant.status = TenantStatus.active.value

    subscription = session.execute(
        select(Subscription).where(Subscription.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if subscription is None:
        session.add(
            Subscription(
                tenant_id=tenant.id,
                plan_id=free_plan.id,
                status="active",
            )
        )
    return tenant


def run_seed(session: Session | None = None) -> None:
    own_session = session is None
    session = session or SessionLocal()
    try:
        plans = seed_plans(session)
        tenant = seed_demo_tenant(session, plans[FREE_PLAN_CODE])
        session.commit()
        logger.info("seed_complete demo_tenant_id=%s", tenant.id)
        print(f"Seed complete. Demo tenant id: {tenant.id}")
        print("Send headers: X-Tenant-Id and X-Dev-Token (see .env.example).")
    except Exception:
        session.rollback()
        raise
    finally:
        if own_session:
            session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run_seed()


if __name__ == "__main__":
    main()
