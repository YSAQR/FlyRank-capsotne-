from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.plan import Plan
from app.db.models.subscription import Subscription
from app.db.models.tenant import Tenant


class TenantRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, tenant_id: UUID) -> Tenant | None:
        return self.session.get(Tenant, tenant_id)

    def add(self, tenant: Tenant) -> Tenant:
        self.session.add(tenant)
        self.session.flush()
        return tenant

    def get_plan_by_code(self, code: str) -> Plan | None:
        return self.session.execute(select(Plan).where(Plan.code == code)).scalar_one_or_none()

    def get_subscription_for_update(self, tenant_id: UUID) -> Subscription | None:
        return self.session.execute(
            select(Subscription)
            .where(Subscription.tenant_id == tenant_id)
            .with_for_update()
        ).scalar_one_or_none()

    def get_subscription(self, tenant_id: UUID) -> Subscription | None:
        return self.session.execute(
            select(Subscription).where(Subscription.tenant_id == tenant_id)
        ).scalar_one_or_none()
