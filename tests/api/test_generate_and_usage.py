from tests.conftest import DEV_TOKEN, generate_body, new_tenant


def test_generate_records_usage_once(client, auth_headers) -> None:
    headers = {**auth_headers, "Idempotency-Key": "same-key"}
    first = client.post("/generate", headers=headers, json=generate_body())
    second = client.post("/generate", headers=headers, json=generate_body())
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["idempotent_replay"] is True
    assert first.json()["generation_id"] == second.json()["generation_id"]
    usage = client.get("/usage", headers=auth_headers)
    assert usage.status_code == 200
    body = usage.json()
    assert body["api_calls"]["used"] == 1
    assert body["ai_tokens"]["used"] == 235
    assert body["cost"]["amount"] == 1_791_000
    assert body["cost"]["unit"] == "nano_usd"


def test_conflicting_idempotency_key(client, auth_headers) -> None:
    headers = {**auth_headers, "Idempotency-Key": "conflict-key"}
    first = client.post("/generate", headers=headers, json=generate_body())
    assert first.status_code == 200
    second = client.post("/generate", headers=headers, json=generate_body(input_tokens=121))
    assert second.status_code == 409
    assert second.json()["error"] == "IDEMPOTENCY_KEY_REUSED"


def test_tenant_isolation(client, auth_headers) -> None:
    client.post("/generate", headers={**auth_headers, "Idempotency-Key": "a1"}, json=generate_body())
    other = new_tenant(client)
    other_headers = {"X-Dev-Token": DEV_TOKEN, "X-Tenant-Id": other}
    usage = client.get("/usage", headers=other_headers)
    assert usage.json()["api_calls"]["used"] == 0
    assert usage.json()["ai_tokens"]["used"] == 0
    assert usage.json()["cost"]["amount"] == 0


def test_missing_idempotency_key(client, auth_headers) -> None:
    response = client.post("/generate", headers=auth_headers, json=generate_body())
    assert response.status_code == 400
