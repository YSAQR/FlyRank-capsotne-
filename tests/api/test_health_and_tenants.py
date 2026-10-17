from tests.conftest import DEV_TOKEN


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_tenant_requires_token(client) -> None:
    response = client.post("/tenants", json={"name": "x"})
    assert response.status_code == 401


def test_create_tenant(client) -> None:
    response = client.post("/tenants", headers={"X-Dev-Token": DEV_TOKEN}, json={"name": "Acme"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme"
    assert body["plan_code"] == "free"
    assert body["subscription_status"] == "active"


def test_validation_error_is_422(client, auth_headers) -> None:
    response = client.post(
        "/generate",
        headers={**auth_headers, "Idempotency-Key": "k"},
        json={"prompt": "hi", "input_tokens": -1, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_unknown_tenant_is_404(client) -> None:
    response = client.get(
        "/usage",
        headers={
            "X-Dev-Token": DEV_TOKEN,
            "X-Tenant-Id": "00000000-0000-0000-0000-000000000099",
        },
    )
    assert response.status_code == 404
