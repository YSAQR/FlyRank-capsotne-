from sqlalchemy import text
from tests.conftest import DEV_TOKEN, generate_body, new_tenant


def _set_free_quotas(engine, api: int, tokens: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE plans SET monthly_api_call_quota=:api, monthly_ai_token_quota=:tokens WHERE code='free'"
            ),
            {"api": api, "tokens": tokens},
        )


def _headers(tenant_id: str, key: str) -> dict[str, str]:
    return {
        "X-Dev-Token": DEV_TOKEN,
        "X-Tenant-Id": tenant_id,
        "Idempotency-Key": key,
    }


def test_usage_below_limit_accepted(client, engine) -> None:
    _set_free_quotas(engine, api=10, tokens=1000)
    tenant = new_tenant(client)
    response = client.post("/generate", headers=_headers(tenant, "below"), json=generate_body())
    assert response.status_code == 200


def test_usage_exactly_at_limit_accepted(client, engine) -> None:
    _set_free_quotas(engine, api=1, tokens=235)
    tenant = new_tenant(client)
    response = client.post("/generate", headers=_headers(tenant, "exact"), json=generate_body())
    assert response.status_code == 200
    usage = client.get("/usage", headers={"X-Dev-Token": DEV_TOKEN, "X-Tenant-Id": tenant})
    assert usage.json()["api_calls"]["used"] == 1
    assert usage.json()["ai_tokens"]["used"] == 235
    assert usage.json()["api_calls"]["remaining"] == 0
    assert usage.json()["ai_tokens"]["remaining"] == 0


def test_usage_beyond_limit_rejected(client, engine) -> None:
    _set_free_quotas(engine, api=1, tokens=235)
    tenant = new_tenant(client)
    client.post("/generate", headers=_headers(tenant, "fill"), json=generate_body())
    response = client.post("/generate", headers=_headers(tenant, "over"), json=generate_body())
    assert response.status_code == 429
    assert response.json()["error"] == "QUOTA_EXCEEDED"
    assert "Retry-After" in response.headers


def test_quantity_alone_exceeds_quota(client, engine) -> None:
    _set_free_quotas(engine, api=10, tokens=100)
    tenant = new_tenant(client)
    response = client.post("/generate", headers=_headers(tenant, "huge"), json=generate_body())
    assert response.status_code == 429


def test_already_at_limit(client, engine) -> None:
    _set_free_quotas(engine, api=1, tokens=10_000)
    tenant = new_tenant(client)
    assert client.post("/generate", headers=_headers(tenant, "one"), json=generate_body()).status_code == 200
    second = client.post("/generate", headers=_headers(tenant, "two"), json=generate_body())
    assert second.status_code == 429


def test_replay_does_not_consume_quota_again(client, engine) -> None:
    _set_free_quotas(engine, api=1, tokens=235)
    tenant = new_tenant(client)
    headers = _headers(tenant, "replay")
    assert client.post("/generate", headers=headers, json=generate_body()).status_code == 200
    replay = client.post("/generate", headers=headers, json=generate_body())
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True


def test_canceled_subscription_returns_402(client, engine) -> None:
    tenant = new_tenant(client)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE subscriptions SET status='canceled' WHERE tenant_id=:tid"),
            {"tid": tenant},
        )
    response = client.post("/generate", headers=_headers(tenant, "paid"), json=generate_body())
    assert response.status_code == 402
    assert response.json()["error"] == "PAYMENT_REQUIRED"
