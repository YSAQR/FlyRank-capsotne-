from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AppError,
    PaymentRequiredError,
    StripeNotConfiguredError,
    ValidationAppError,
)
from app.db.models.plan import Plan
from app.db.models.stripe_event import StripeEvent
from app.db.models.subscription import Subscription
from app.db.seed import FREE_PLAN_CODE, PRO_PLAN_CODE
from app.repositories.stripe_repository import StripeRepository
from app.repositories.tenant_repository import TenantRepository

logger = logging.getLogger(__name__)


class StripeService:
    def __init__(self, session: Session, settings: Settings | None = None, stripe_module: Any = stripe) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.stripe = stripe_module
        self.tenants = TenantRepository(session)
        self.stripe_repo = StripeRepository(session)
        self.stripe.api_key = self.settings.stripe_secret_key

    def create_checkout_session(self, tenant_id: UUID) -> dict[str, str]:
        if not self.settings.stripe_configured:
            raise StripeNotConfiguredError()

        subscription = self.tenants.get_subscription_for_update(tenant_id)
        if subscription is None:
            raise PaymentRequiredError("No subscription exists for this tenant.")
        pro = self.stripe_repo.get_plan_by_code(PRO_PLAN_CODE)
        if pro is None:
            raise ValidationAppError("Pro plan is not seeded.")

        current_plan = self.session.get(Plan, subscription.plan_id)
        if current_plan is not None and current_plan.code == PRO_PLAN_CODE and subscription.is_billable:
            raise ValidationAppError("Tenant already has an active Pro subscription.")

        customer_id = subscription.stripe_customer_id
        if not customer_id:
            customer = self.stripe.Customer.create(
                metadata={"tenant_id": str(tenant_id)},
                name=f"tenant-{tenant_id}",
            )
            customer_id = customer["id"]
            subscription.stripe_customer_id = customer_id
            self.session.flush()

        checkout = self.stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            client_reference_id=str(tenant_id),
            success_url=self.settings.checkout_success_url,
            cancel_url=self.settings.checkout_cancel_url,
            line_items=[{"price": self.settings.stripe_pro_price_id, "quantity": 1}],
            metadata={"tenant_id": str(tenant_id)},
            subscription_data={"metadata": {"tenant_id": str(tenant_id)}},
        )
        self.session.commit()
        return {
            "checkout_url": checkout["url"],
            "session_id": checkout["id"],
            "stripe_customer_id": customer_id,
        }

    def construct_event(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        if not signature:
            raise AppError("INVALID_STRIPE_SIGNATURE", "Stripe-Signature header is missing.", 400)
        try:
            event = self.stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=self.settings.stripe_webhook_secret,
            )
        except Exception as exc:
            logger.info("stripe_signature_rejected")
            raise AppError("INVALID_STRIPE_SIGNATURE", "Invalid Stripe webhook signature.", 400) from exc
        if hasattr(event, "to_dict"):
            return event.to_dict()
        return dict(event)

    def process_event(self, event: dict[str, Any]) -> dict[str, str]:
        event_id = event["id"]
        event_type = event["type"]
        digest = hashlib.sha256(repr(event.get("data", {})).encode("utf-8")).hexdigest()

        nested = self.session.begin_nested()
        self.session.add(
            StripeEvent(
                id=event_id,
                event_type=event_type,
                payload_digest=digest,
                metadata_={"type": event_type},
            )
        )
        try:
            self.session.flush()
            nested.commit()
        except IntegrityError:
            nested.rollback()
            logger.info("stripe_event_duplicate event_id=%s", event_id)
            return {"status": "duplicate", "event_id": event_id}

        try:
            if event_type == "checkout.session.completed":
                self._on_checkout_completed(event["data"]["object"])
            elif event_type == "customer.subscription.updated":
                self._on_subscription_updated(event["data"]["object"])
            elif event_type == "customer.subscription.deleted":
                self._on_subscription_deleted(event["data"]["object"])
            else:
                logger.info("stripe_event_ignored type=%s", event_type)
            self.session.commit()
        except Exception:
            self.session.rollback()
            logger.exception("stripe_event_failed event_id=%s", event_id)
            raise

        return {"status": "processed", "event_id": event_id}

    def _on_checkout_completed(self, session_obj: dict[str, Any]) -> None:
        tenant_id = session_obj.get("client_reference_id") or (session_obj.get("metadata") or {}).get(
            "tenant_id"
        )
        customer_id = session_obj.get("customer")
        stripe_sub_id = session_obj.get("subscription")
        subscription = None
        if tenant_id:
            subscription = self.tenants.get_subscription(UUID(str(tenant_id)))
        if subscription is None and customer_id:
            subscription = self.stripe_repo.get_subscription_by_customer(str(customer_id))
        if subscription is None:
            logger.info("stripe_checkout_unmatched")
            return
        if stripe_sub_id:
            remote = self.stripe.Subscription.retrieve(stripe_sub_id)
            self._apply_subscription(subscription, remote)

    def _on_subscription_updated(self, stripe_sub: dict[str, Any]) -> None:
        subscription = self._find_subscription(stripe_sub)
        if subscription is None:
            return
        self._apply_subscription(subscription, stripe_sub)

    def _on_subscription_deleted(self, stripe_sub: dict[str, Any]) -> None:
        subscription = self._find_subscription(stripe_sub)
        if subscription is None:
            return
        free = self.stripe_repo.get_plan_by_code(FREE_PLAN_CODE)
        if free is None:
            raise ValidationAppError("Free plan is not seeded.")
        subscription.plan_id = free.id
        subscription.status = "canceled"
        subscription.stripe_subscription_id = stripe_sub.get("id") or subscription.stripe_subscription_id
        subscription.current_period_end = datetime.now(UTC)

    def _find_subscription(self, stripe_sub: dict[str, Any]) -> Subscription | None:
        sub_id = stripe_sub.get("id")
        found = self.stripe_repo.get_subscription_by_stripe_id(sub_id) if sub_id else None
        if found:
            return found
        customer = stripe_sub.get("customer")
        if customer:
            return self.stripe_repo.get_subscription_by_customer(str(customer))
        metadata = stripe_sub.get("metadata") or {}
        tenant_id = metadata.get("tenant_id")
        if tenant_id:
            return self.tenants.get_subscription(UUID(str(tenant_id)))
        return None

    def _apply_subscription(self, local: Subscription, stripe_sub: Any) -> None:
        data = stripe_sub.to_dict() if hasattr(stripe_sub, "to_dict") else dict(stripe_sub)
        status = str(data.get("status") or "active")
        local.status = status
        local.stripe_subscription_id = data.get("id") or local.stripe_subscription_id
        if data.get("customer"):
            local.stripe_customer_id = str(data.get("customer"))
        start = data.get("current_period_start")
        end = data.get("current_period_end")
        if start:
            local.current_period_start = datetime.fromtimestamp(int(start), tz=UTC)
        if end:
            local.current_period_end = datetime.fromtimestamp(int(end), tz=UTC)
        if status in {"active", "trialing"}:
            pro = self.stripe_repo.get_plan_by_code(PRO_PLAN_CODE)
            if pro is not None:
                local.plan_id = pro.id
        elif status in {"canceled", "unpaid", "incomplete_expired"}:
            free = self.stripe_repo.get_plan_by_code(FREE_PLAN_CODE)
            if free is not None:
                local.plan_id = free.id
