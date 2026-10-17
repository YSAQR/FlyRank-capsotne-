from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
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


@pytest.mark.concurrency
@pytest.mark.integration
def test_concurrent_duplicate_keys_create_one_event(client, auth_headers) -> None:
    headers = {**auth_headers, "Idempotency-Key": "concurrent-dup"}

    def call() -> int:
        return client.post("/generate", headers=headers, json=generate_body()).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = [f.result() for f in as_completed([pool.submit(call) for _ in range(8)])]
    assert codes.count(200) == 8
    usage = client.get("/usage", headers=auth_headers).json()
    assert usage["api_calls"]["used"] == 1
    assert usage["ai_tokens"]["used"] == 235


@pytest.mark.concurrency
@pytest.mark.integration
def test_concurrent_requests_cannot_overspend_quota(client, engine) -> None:
    _set_free_quotas(engine, api=1, tokens=10_000)
    tenant = new_tenant(client)

    def call(i: int) -> int:
        return client.post(
            "/generate",
            headers={
                "X-Dev-Token": DEV_TOKEN,
                "X-Tenant-Id": tenant,
                "Idempotency-Key": f"race-{i}",
            },
            json=generate_body(),
        ).status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = [f.result() for f in as_completed([pool.submit(call, i) for i in range(6)])]
    assert codes.count(200) == 1
    assert codes.count(429) == 5
    usage = client.get("/usage", headers={"X-Dev-Token": DEV_TOKEN, "X-Tenant-Id": tenant}).json()
    assert usage["api_calls"]["used"] == 1
