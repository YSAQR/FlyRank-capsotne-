from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.plan import Plan
from app.db.models.stripe_event import StripeEvent
from app.db.models.subscription import Subscription


class StripeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_event(self, event_id: str) -> StripeEvent | None:
        return self.session.get(StripeEvent, event_id)

    def add_event(self, event: StripeEvent) -> None:
        self.session.add(event)

    def get_subscription_by_stripe_id(self, stripe_subscription_id: str) -> Subscription | None:
        return self.session.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
        ).scalar_one_or_none()

    def get_subscription_by_customer(self, stripe_customer_id: str) -> Subscription | None:
        return self.session.execute(
            select(Subscription).where(Subscription.stripe_customer_id == stripe_customer_id)
        ).scalar_one_or_none()

    def get_plan_by_code(self, code: str) -> Plan | None:
        return self.session.execute(select(Plan).where(Plan.code == code)).scalar_one_or_none()
