from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationAppError
from app.db.models.subscription import Subscription
from app.db.models.tenant import Tenant, TenantStatus
from app.db.seed import FREE_PLAN_CODE
from app.repositories.tenant_repository import TenantRepository
from app.schemas.tenants import TenantCreate, TenantRead


class SubscriptionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.tenants = TenantRepository(session)

    def create_tenant(self, payload: TenantCreate) -> TenantRead:
        plan = self.tenants.get_plan_by_code(FREE_PLAN_CODE)
        if plan is None:
            raise ValidationAppError("Free plan is not seeded. Run: python -m app.db.seed")
        tenant = Tenant(name=payload.name.strip(), status=TenantStatus.active.value)
        self.tenants.add(tenant)
        self.session.add(Subscription(tenant_id=tenant.id, plan_id=plan.id, status="active"))
        self.session.commit()
        self.session.refresh(tenant)
        return TenantRead(
            id=tenant.id,
            name=tenant.name,
            status=tenant.status,
            created_at=tenant.created_at,
            plan_code=plan.code,
            subscription_status="active",
        )

    def get_locked(self, tenant_id: UUID) -> Subscription | None:
        return self.tenants.get_subscription_for_update(tenant_id)
