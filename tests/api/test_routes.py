from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from invoice_system.api.app import app, get_application
from invoice_system.api.auth import get_auth_service
from invoice_system.auth import build_auth
from invoice_system.factory import build_application


@pytest.fixture
def auth(tmp_path):
    ctx = build_auth(tmp_path / "auth.db")
    ctx.service.create_user("owner@acme.test", "correct horse battery staple")
    yield ctx
    ctx.close()


@pytest.fixture
def client(tmp_path, monkeypatch, auth):
    # The lifespan builds its own Application/Auth from env vars even though
    # the dependency overrides below replace them for route handlers - point
    # both at throwaway paths so it doesn't touch the real default files.
    monkeypatch.setenv("INVOICE_SYSTEM_DB", str(tmp_path / "lifespan.db"))
    monkeypatch.setenv("INVOICE_SYSTEM_AUTH_DB", str(tmp_path / "lifespan-auth.db"))

    application = build_application(tmp_path / "test.db")
    app.dependency_overrides[get_application] = lambda: application
    app.dependency_overrides[get_auth_service] = lambda: auth.service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    application.close()


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/auth/login", json={"email": "owner@acme.test", "password": "correct horse battery staple"}
    )
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_healthz_is_public(client):
    response = client.get("/healthz")
    assert response.status_code == 200


def test_protected_route_without_token_is_rejected(client):
    response = client.get("/accounts")
    assert response.status_code == 401


def test_login_with_wrong_password_is_rejected(client):
    response = client.post("/auth/login", json={"email": "owner@acme.test", "password": "wrong"})
    assert response.status_code == 401


def test_login_then_me(client, auth_headers):
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "owner@acme.test"


def test_logout_revokes_token(client, auth_headers):
    response = client.post("/auth/logout", headers=auth_headers)
    assert response.status_code == 204

    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 401


def test_account_quote_invoice_flow(client, auth_headers):
    response = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address": "1 Main St"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    account_id = response.json()["id"]

    response = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers)
    assert response.status_code == 201
    quote_id = response.json()["id"]

    response = client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["total"] == "100.00"

    response = client.post(f"/quotes/{quote_id}/send", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["number"] == "Q-0001"

    response = client.get(f"/quotes/{quote_id}/pdf", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    response = client.post(f"/quotes/{quote_id}/convert", headers=auth_headers)
    assert response.status_code == 201
    invoice_id = response.json()["id"]
    assert response.json()["quote_id"] == quote_id

    response = client.get(f"/invoices/{invoice_id}/pdf", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    response = client.post(f"/invoices/{invoice_id}/send", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["number"] == "INV-0001"


def test_get_missing_account_returns_404(client, auth_headers):
    response = client.get("/accounts/999", headers=auth_headers)
    assert response.status_code == 404


def test_line_item_rejects_non_decimal_quantity(client, auth_headers):
    response = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address": "1 Main St"},
        headers=auth_headers,
    )
    account_id = response.json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "not-a-number", "unit_price": "1.00"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_sending_quote_with_no_line_items_returns_422(client, auth_headers):
    response = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address": "1 Main St"},
        headers=auth_headers,
    )
    account_id = response.json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.post(f"/quotes/{quote_id}/send", headers=auth_headers)
    assert response.status_code == 422


def test_business_profile_requires_auth(client):
    response = client.get("/settings/business-profile")
    assert response.status_code == 401


def test_business_profile_defaults_before_first_save(client, auth_headers):
    response = client.get("/settings/business-profile", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["title"] is None
    assert body["first_name"] == ""
    assert body["last_name"] == ""
    assert body["business_name"] == ""
    assert body["business_address"] is None
    assert body["payment_terms_days"] == 30
    assert body["utr"] is None
    assert body["vat_number"] is None


def test_saving_business_profile_persists_and_is_returned_on_refetch(client, auth_headers):
    response = client.put(
        "/settings/business-profile",
        json={
            "title": "Dr",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "business_name": "Acme Consulting",
            "business_address": "1 Main St",
            "payment_terms_days": 14,
            "utr": "1234567890",
            "vat_number": "GB123456789",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["business_name"] == "Acme Consulting"
    assert response.json()["payment_terms_days"] == 14

    response = client.get("/settings/business-profile", headers=auth_headers)
    assert response.json()["title"] == "Dr"
    assert response.json()["first_name"] == "Ada"
    assert response.json()["utr"] == "1234567890"
    assert response.json()["vat_number"] == "GB123456789"


def test_business_address_is_optional(client, auth_headers):
    response = client.put(
        "/settings/business-profile",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "business_name": "Acme Consulting",
            "payment_terms_days": 30,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["business_address"] is None


def test_saving_business_profile_without_a_name_returns_422(client, auth_headers):
    response = client.put(
        "/settings/business-profile",
        json={"first_name": "Ada", "last_name": "Lovelace", "business_name": "", "payment_terms_days": 30},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_saving_business_profile_without_first_name_returns_422(client, auth_headers):
    response = client.put(
        "/settings/business-profile",
        json={"first_name": "", "last_name": "Lovelace", "business_name": "Acme", "payment_terms_days": 30},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_payment_terms_from_profile_drive_the_invoice_due_date(client, auth_headers):
    client.put(
        "/settings/business-profile",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "business_name": "Acme Consulting",
            "payment_terms_days": 5,
        },
        headers=auth_headers,
    )

    account_id = client.post(
        "/accounts",
        json={"business_name": "Client Co", "email": "a@b.test", "address": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]
    client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )
    client.post(f"/quotes/{quote_id}/send", headers=auth_headers)
    invoice = client.post(f"/quotes/{quote_id}/convert", headers=auth_headers).json()

    response = client.post(f"/invoices/{invoice['id']}/send", headers=auth_headers)
    sent = response.json()
    expected_due = date.fromisoformat(sent["issue_date"]) + timedelta(days=5)
    assert sent["due_date"] == expected_due.isoformat()


def test_pdf_still_renders_with_no_business_profile_set(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Client Co", "email": "a@b.test", "address": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.get(f"/quotes/{quote_id}/pdf", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
