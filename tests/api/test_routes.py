import pytest
from fastapi.testclient import TestClient

from invoice_system.api.app import app, get_application
from invoice_system.factory import build_application


@pytest.fixture
def client(tmp_path, monkeypatch):
    # The lifespan builds its own Application from INVOICE_SYSTEM_DB even though
    # the dependency override below replaces it for route handlers - point it at
    # a throwaway path so it doesn't touch the real default db file.
    monkeypatch.setenv("INVOICE_SYSTEM_DB", str(tmp_path / "lifespan.db"))

    application = build_application(tmp_path / "test.db")
    app.dependency_overrides[get_application] = lambda: application
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    application.close()


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200


def test_account_quote_invoice_flow(client):
    response = client.post(
        "/accounts", json={"business_name": "Acme", "email": "a@b.test", "address": "1 Main St"}
    )
    assert response.status_code == 201
    account_id = response.json()["id"]

    response = client.post("/quotes", json={"account_id": account_id})
    assert response.status_code == 201
    quote_id = response.json()["id"]

    response = client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "1", "unit_price": "100.00"},
    )
    assert response.status_code == 201
    assert response.json()["total"] == "100.00"

    response = client.post(f"/quotes/{quote_id}/send")
    assert response.status_code == 200
    assert response.json()["number"] == "Q-0001"

    response = client.get(f"/quotes/{quote_id}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    response = client.post(f"/quotes/{quote_id}/convert")
    assert response.status_code == 201
    invoice_id = response.json()["id"]
    assert response.json()["quote_id"] == quote_id

    response = client.get(f"/invoices/{invoice_id}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    response = client.post(f"/invoices/{invoice_id}/send")
    assert response.status_code == 200
    assert response.json()["number"] == "INV-0001"


def test_get_missing_account_returns_404(client):
    response = client.get("/accounts/999")
    assert response.status_code == 404


def test_line_item_rejects_non_decimal_quantity(client):
    response = client.post(
        "/accounts", json={"business_name": "Acme", "email": "a@b.test", "address": "1 Main St"}
    )
    account_id = response.json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}).json()["id"]

    response = client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "not-a-number", "unit_price": "1.00"},
    )
    assert response.status_code == 422


def test_sending_quote_with_no_line_items_returns_422(client):
    response = client.post(
        "/accounts", json={"business_name": "Acme", "email": "a@b.test", "address": "1 Main St"}
    )
    account_id = response.json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}).json()["id"]

    response = client.post(f"/quotes/{quote_id}/send")
    assert response.status_code == 422
