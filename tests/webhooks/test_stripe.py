from unittest.mock import MagicMock

from app.core.config import Settings, get_settings
from app.db.seed import DEMO_TENANT_ID
from app.services.stripe_service import StripeService
from sqlalchemy.orm import sessionmaker
from tests.conftest import DEV_TOKEN


def test_invalid_webhook_signature_returns_400(client) -> None:
    response = client.post(
        "/webhooks/stripe",
        content=b'{"id":"evt_1"}',
        headers={"Stripe-Signature": "t=1,v1=deadbeef", "Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_STRIPE_SIGNATURE"


def test_missing_signature_returns_400(client) -> None:
    response = client.post("/webhooks/stripe", content=b"{}")
    assert response.status_code == 400


def test_subscription_updated_and_duplicate(client, engine) -> None:
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    service = StripeService(db, settings=get_settings(), stripe_module=MagicMock())
    event = {
        "id": "evt_sub_updated_1",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_test_1",
                "customer": "cus_test_1",
                "status": "active",
                "current_period_start": 1_700_000_000,
                "current_period_end": 1_702_000_000,
                "metadata": {"tenant_id": str(DEMO_TENANT_ID)},
            }
        },
    }
    assert service.process_event(event)["status"] == "processed"
    db.close()

    db2 = Session()
    service2 = StripeService(db2, settings=get_settings(), stripe_module=MagicMock())
    assert service2.process_event(event)["status"] == "duplicate"
    db2.close()

    usage = client.get(
        "/usage",
        headers={"X-Dev-Token": DEV_TOKEN, "X-Tenant-Id": str(DEMO_TENANT_ID)},
    )
    assert usage.json()["plan_code"] == "pro"
    assert usage.json()["subscription_status"] == "active"
    assert usage.json()["api_calls"]["allowed"] == 100_000


def test_subscription_deleted_returns_to_free(client, engine) -> None:
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    service = StripeService(db, settings=get_settings(), stripe_module=MagicMock())
    service.process_event(
        {
            "id": "evt_sub_del_1",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test_1",
                    "customer": "cus_test_1",
                    "status": "canceled",
                    "metadata": {"tenant_id": str(DEMO_TENANT_ID)},
                }
            },
        }
    )
    db.close()
    usage = client.get(
        "/usage",
        headers={"X-Dev-Token": DEV_TOKEN, "X-Tenant-Id": str(DEMO_TENANT_ID)},
    )
    assert usage.json()["plan_code"] == "free"
    assert usage.json()["subscription_status"] == "canceled"


def test_checkout_requires_stripe_config(client, auth_headers) -> None:
    response = client.post("/billing/checkout", headers=auth_headers)
    assert response.status_code == 503
    assert response.json()["error"] == "STRIPE_NOT_CONFIGURED"


def test_checkout_mocked(engine, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(Settings, "stripe_configured", property(lambda self: True))
    fake_stripe = MagicMock()
    fake_stripe.Customer.create.return_value = {"id": "cus_abc"}
    fake_stripe.checkout.Session.create.return_value = {
        "id": "cs_test_1",
        "url": "https://checkout.stripe.com/c/pay/cs_test_1",
    }
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    service = StripeService(db, settings=settings, stripe_module=fake_stripe)
    result = service.create_checkout_session(DEMO_TENANT_ID)
    assert result["session_id"] == "cs_test_1"
    assert result["stripe_customer_id"] == "cus_abc"
    db.close()
