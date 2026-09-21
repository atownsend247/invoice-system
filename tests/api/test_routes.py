from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from invoice_system.api.app import app, get_application
from invoice_system.api.auth import get_application as get_application_for_auth_routes
from invoice_system.api.auth import get_auth_service
from invoice_system.auth import build_auth
from invoice_system.factory import Application, build_application


@pytest.fixture
def auth(tmp_path):
    ctx = build_auth(tmp_path / "auth.db")
    ctx.service.create_user("owner@acme.test", "correct horse battery staple")
    ctx.service.create_user("other@acme.test", "correct horse battery staple")
    yield ctx
    ctx.close()


@pytest.fixture
def application(tmp_path) -> Application:
    app_ = build_application(tmp_path / "test.db", attachments_dir=tmp_path / "attachments")
    yield app_
    app_.close()


@pytest.fixture
def client(tmp_path, monkeypatch, auth, application):
    # The lifespan builds its own Application/Auth from env vars even though
    # the dependency overrides below replace them for route handlers - point
    # both at throwaway paths so it doesn't touch the real default files.
    monkeypatch.setenv("INVOICE_SYSTEM_DB", str(tmp_path / "lifespan.db"))
    monkeypatch.setenv("INVOICE_SYSTEM_AUTH_DB", str(tmp_path / "lifespan-auth.db"))
    monkeypatch.setenv("INVOICE_SYSTEM_ATTACHMENTS_DIR", str(tmp_path / "lifespan-attachments"))

    # api/auth.py can't import api/app.py's get_application (circular import
    # - see its own comment), so it defines its own identical one-liner;
    # FastAPI's dependency_overrides is keyed by the exact function object,
    # so both need overriding for a route on either router to see this
    # test's `application` instead of the lifespan's real one.
    app.dependency_overrides[get_application] = lambda: application
    app.dependency_overrides[get_application_for_auth_routes] = lambda: application
    app.dependency_overrides[get_auth_service] = lambda: auth.service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/auth/login", json={"email": "owner@acme.test", "password": "correct horse battery staple"}
    )
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_auth_headers(client):
    response = client.post(
        "/auth/login", json={"email": "other@acme.test", "password": "correct horse battery staple"}
    )
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_healthz_is_public(client):
    response = client.get("/healthz")
    assert response.status_code == 200


def test_lifespan_derives_db_and_auth_paths_from_storage_dir_env_var(tmp_path, monkeypatch):
    # Deliberately not the `client` fixture - that one always sets
    # INVOICE_SYSTEM_DB/AUTH_DB/ATTACHMENTS_DIR explicitly (so its own
    # lifespan-built app - unused by any route, since dependency_overrides
    # replaces it - never touches this env var at all). This test exists
    # specifically to prove the *lifespan itself* derives both db paths
    # from INVOICE_SYSTEM_STORAGE_DIR when none of the three per-path
    # overrides are set - see api/app.py's lifespan.
    storage_dir = tmp_path / "my-storage"
    monkeypatch.setenv("INVOICE_SYSTEM_STORAGE_DIR", str(storage_dir))
    monkeypatch.delenv("INVOICE_SYSTEM_DB", raising=False)
    monkeypatch.delenv("INVOICE_SYSTEM_AUTH_DB", raising=False)
    monkeypatch.delenv("INVOICE_SYSTEM_ATTACHMENTS_DIR", raising=False)

    with TestClient(app) as test_client:
        assert test_client.get("/healthz").status_code == 200

    assert (storage_dir / "db" / "invoice_system.db").exists()
    assert (storage_dir / "db" / "auth.db").exists()


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


def test_register_validate_and_full_flow(client, application):
    # There's deliberately no API route to create an invite (CLI-only, see
    # CLAUDE.md) - tests reach into the service directly, same as the CLI
    # would.
    invite = application.registration_invites.create_invite()

    response = client.get("/auth/register/validate", params={"token": invite.token})
    assert response.status_code == 200
    assert response.json() == {"valid": True}

    response = client.post(
        "/auth/register",
        json={"token": invite.token, "email": "new-user@example.test", "password": "correct-horse-1"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "new-user@example.test"

    # The new login actually works.
    response = client.post(
        "/auth/login", json={"email": "new-user@example.test", "password": "correct-horse-1"}
    )
    assert response.status_code == 200


def test_register_rejects_an_unknown_token(client):
    response = client.get("/auth/register/validate", params={"token": "does-not-exist"})
    assert response.status_code == 404

    response = client.post(
        "/auth/register",
        json={"token": "does-not-exist", "email": "a@b.test", "password": "correct-horse-1"},
    )
    assert response.status_code == 404


def test_register_rejects_an_expired_token(client, application):
    invite = application.registration_invites.create_invite(expires_in_days=-1)

    response = client.get("/auth/register/validate", params={"token": invite.token})
    assert response.status_code == 404

    response = client.post(
        "/auth/register",
        json={"token": invite.token, "email": "a@b.test", "password": "correct-horse-1"},
    )
    assert response.status_code == 404


def test_register_rejects_reusing_a_consumed_token(client, application):
    invite = application.registration_invites.create_invite()
    first = client.post(
        "/auth/register",
        json={"token": invite.token, "email": "first@example.test", "password": "correct-horse-1"},
    )
    assert first.status_code == 201

    second = client.post(
        "/auth/register",
        json={"token": invite.token, "email": "second@example.test", "password": "correct-horse-1"},
    )
    assert second.status_code == 404

    response = client.get("/auth/register/validate", params={"token": invite.token})
    assert response.status_code == 404


def test_register_rejects_a_duplicate_email(client, application):
    invite = application.registration_invites.create_invite()
    response = client.post(
        "/auth/register",
        json={"token": invite.token, "email": "owner@acme.test", "password": "correct-horse-1"},
    )
    assert response.status_code == 409


def test_register_rejects_a_short_password(client, application):
    invite = application.registration_invites.create_invite()
    response = client.post(
        "/auth/register",
        json={"token": invite.token, "email": "new-user@example.test", "password": "short"},
    )
    assert response.status_code == 422


def test_account_quote_invoice_flow(client, auth_headers):
    response = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    account_id = response.json()["id"]

    response = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers)
    assert response.status_code == 201
    quote_id = response.json()["id"]
    assert len(response.json()["events"]) == 1
    assert response.json()["events"][0]["event_type"] == "created"

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
    assert response.json()["events"][0] == {
        "id": response.json()["events"][0]["id"],
        "event_type": "status_changed",
        "from_status": "draft",
        "to_status": "sent",
        "occurred_at": response.json()["events"][0]["occurred_at"],
    }

    response = client.get(f"/quotes/{quote_id}/pdf", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    response = client.post(f"/quotes/{quote_id}/convert", headers=auth_headers)
    assert response.status_code == 201
    invoice_id = response.json()["id"]
    assert response.json()["quote_id"] == quote_id
    assert response.json()["events"][0]["event_type"] == "created"

    response = client.get(f"/invoices/{invoice_id}/pdf", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    response = client.post(f"/invoices/{invoice_id}/send", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["number"] == "INV-0001"
    assert response.json()["events"][0]["event_type"] == "status_changed"


def test_create_quote_with_issue_date_computes_expiry_from_business_profile_validity(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    client.put(
        "/settings/business-profile",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "business_name": "Acme",
            "payment_terms_days": 30,
            "quote_validity_days": 45,
        },
        headers=auth_headers,
    )

    response = client.post(
        "/quotes",
        json={"account_id": account_id, "issue_date": "2026-01-01"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["issue_date"] == "2026-01-01"
    assert body["expiry_date"] == "2026-02-15"  # + quote_validity_days (45)


def test_convert_quote_accepts_a_backdated_issue_date(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]
    client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )
    client.post(f"/quotes/{quote_id}/send", headers=auth_headers)

    response = client.post(
        f"/quotes/{quote_id}/convert", json={"issue_date": "2025-11-01"}, headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["issue_date"] == "2025-11-01"


def test_list_accounts_paginates_and_filters_by_query(client, auth_headers):
    for name, email in [("Northwind Traders", "billing@northwind.test"), ("Acme Ltd", "a@acme.test")]:
        client.post(
            "/accounts",
            json={"business_name": name, "email": email, "address_line1": "1 Main St"},
            headers=auth_headers,
        )

    response = client.get("/accounts?page=1&page_size=1", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["total"] == 2

    response = client.get("/accounts?query=northwind", headers=auth_headers)
    body = response.json()
    assert [a["business_name"] for a in body["items"]] == ["Northwind Traders"]
    assert body["total"] == 1


def test_list_accounts_rejects_invalid_page_size(client, auth_headers):
    response = client.get("/accounts?page_size=0", headers=auth_headers)
    assert response.status_code == 422


def test_list_quotes_paginates_and_filters_by_account_name_and_status(client, auth_headers):
    acme_id = client.post(
        "/accounts",
        json={"business_name": "Acme Ltd", "email": "a@acme.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    northwind_id = client.post(
        "/accounts",
        json={
            "business_name": "Northwind Traders",
            "email": "a@northwind.test",
            "address_line1": "2 Kings Road",
        },
        headers=auth_headers,
    ).json()["id"]
    draft_id = client.post("/quotes", json={"account_id": acme_id}, headers=auth_headers).json()["id"]
    sent_id = client.post("/quotes", json={"account_id": northwind_id}, headers=auth_headers).json()["id"]
    client.post(
        f"/quotes/{sent_id}/line-items",
        json={"description": "Work", "quantity": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )
    client.post(f"/quotes/{sent_id}/send", headers=auth_headers)

    response = client.get("/quotes?account_name=northwind", headers=auth_headers)
    body = response.json()
    assert [q["id"] for q in body["items"]] == [sent_id]
    assert body["total"] == 1

    response = client.get("/quotes?status=draft", headers=auth_headers)
    body = response.json()
    assert [q["id"] for q in body["items"]] == [draft_id]
    assert body["total"] == 1

    response = client.get("/quotes?page=1&page_size=1", headers=auth_headers)
    assert response.json()["total"] == 2


def test_list_invoices_paginates_and_filters_by_account_name_and_status(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme Ltd", "email": "a@acme.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]
    client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )
    client.post(f"/quotes/{quote_id}/send", headers=auth_headers)
    invoice_id = client.post(f"/quotes/{quote_id}/convert", headers=auth_headers).json()["id"]

    response = client.get("/invoices?account_name=acme", headers=auth_headers)
    body = response.json()
    assert [i["id"] for i in body["items"]] == [invoice_id]
    assert body["total"] == 1

    response = client.get("/invoices?status=draft", headers=auth_headers)
    body = response.json()
    assert [i["id"] for i in body["items"]] == [invoice_id]

    response = client.get("/invoices?status=paid", headers=auth_headers)
    assert response.json()["items"] == []

    # The link a converted quote's own detail page uses to find the
    # invoice it became (QuoteDetailPage.tsx's "View invoice" button).
    response = client.get(f"/invoices?quote_id={quote_id}", headers=auth_headers)
    body = response.json()
    assert [i["id"] for i in body["items"]] == [invoice_id]
    assert body["total"] == 1


def test_account_expense_flow(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]

    response = client.post(
        "/expenses", json={"account_id": account_id, "currency": "GBP"}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    expense_id = body["id"]
    # Unlike a quote, an expense gets its number immediately - there's no
    # draft/send lifecycle (see models.Expense).
    assert body["number"] == "EXP-0001"
    assert body["line_items"] == []

    response = client.post(
        f"/expenses/{expense_id}/line-items",
        json={"description": "Domain renewal", "quantity": "1", "unit_price": "12.00", "tax_rate": "0.20"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["total"] == "14.40"

    response = client.get(f"/expenses/{expense_id}", headers=auth_headers)
    assert response.status_code == 200
    assert [item["description"] for item in response.json()["line_items"]] == ["Domain renewal"]
    item_id = response.json()["line_items"][0]["id"]

    response = client.put(
        f"/expenses/{expense_id}/line-items/{item_id}",
        json={
            "description": "Domain renewal (2yr)",
            "quantity": "2",
            "unit_price": "12.00",
            "tax_rate": "0.20",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["description"] for item in body["line_items"]] == ["Domain renewal (2yr)"]
    assert body["total"] == "28.80"

    response = client.delete(f"/expenses/{expense_id}/line-items/{item_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["line_items"] == []
    assert body["total"] == "0"

    response = client.get(f"/expenses/{expense_id}", headers=auth_headers)
    assert response.json()["line_items"] == []

    response = client.get("/expenses", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get(f"/expenses?account_id={account_id}", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get(f"/expenses/{expense_id}/pdf", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_expense_requires_existing_account(client, auth_headers):
    response = client.post(
        "/expenses", json={"account_id": "does-not-exist", "currency": "GBP"}, headers=auth_headers
    )
    assert response.status_code == 404


def test_create_expense_defaults_expense_date_to_today(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]

    response = client.post("/expenses", json={"account_id": account_id}, headers=auth_headers)
    body = response.json()
    assert body["expense_date"] == body["issue_date"]


def test_create_expense_accepts_an_explicit_expense_date(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]

    response = client.post(
        "/expenses",
        json={"account_id": account_id, "expense_date": "2026-02-20"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["expense_date"] == "2026-02-20"


def test_update_expense_date(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    expense_id = client.post("/expenses", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.put(
        f"/expenses/{expense_id}/expense-date", json={"expense_date": "2026-01-05"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["expense_date"] == "2026-01-05"

    response = client.get(f"/expenses/{expense_id}", headers=auth_headers)
    assert response.json()["expense_date"] == "2026-01-05"


def test_update_expense_date_from_another_login_user_returns_404(client, auth_headers, other_auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Owner's Client", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    expense_id = client.post("/expenses", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.put(
        f"/expenses/{expense_id}/expense-date",
        json={"expense_date": "2026-01-05"},
        headers=other_auth_headers,
    )
    assert response.status_code == 404


def test_expense_from_another_login_user_returns_404(client, auth_headers, other_auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Owner's Client", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    expense_id = client.post("/expenses", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.get(f"/expenses/{expense_id}", headers=other_auth_headers)
    assert response.status_code == 404


def test_expense_line_item_update_and_delete_require_the_item_to_exist(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    expense_id = client.post("/expenses", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.put(
        f"/expenses/{expense_id}/line-items/does-not-exist",
        json={"description": "x", "quantity": "1", "unit_price": "1"},
        headers=auth_headers,
    )
    assert response.status_code == 404

    response = client.delete(f"/expenses/{expense_id}/line-items/does-not-exist", headers=auth_headers)
    assert response.status_code == 404


def test_expense_line_item_update_and_delete_from_another_login_user_return_404(
    client, auth_headers, other_auth_headers
):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    expense_id = client.post("/expenses", json={"account_id": account_id}, headers=auth_headers).json()["id"]
    item_id = client.post(
        f"/expenses/{expense_id}/line-items",
        json={"description": "x", "quantity": "1", "unit_price": "1"},
        headers=auth_headers,
    ).json()["line_items"][0]["id"]

    response = client.put(
        f"/expenses/{expense_id}/line-items/{item_id}",
        json={"description": "y", "quantity": "1", "unit_price": "1"},
        headers=other_auth_headers,
    )
    assert response.status_code == 404

    response = client.delete(f"/expenses/{expense_id}/line-items/{item_id}", headers=other_auth_headers)
    assert response.status_code == 404


def test_account_domain_create_list_update_delete_flow(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]

    response = client.post(
        f"/accounts/{account_id}/domains",
        json={
            "domain_name": "acme.test",
            "expiry_date": "2027-01-01",
            "registrar": "123-Reg",
            "auto_renew": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    domain_id = body["id"]
    assert body["account_id"] == account_id
    assert body["domain_name"] == "acme.test"
    assert body["expiry_date"] == "2027-01-01"
    assert body["registrar"] == "123-Reg"
    assert body["auto_renew"] is True

    response = client.get(f"/accounts/{account_id}/domains", headers=auth_headers)
    assert response.status_code == 200
    assert [d["id"] for d in response.json()] == [domain_id]

    response = client.put(
        f"/accounts/{account_id}/domains/{domain_id}",
        json={
            "domain_name": "acme.co.uk",
            "expiry_date": "2028-01-01",
            "registrar": "GoDaddy",
            "auto_renew": False,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["domain_name"] == "acme.co.uk"
    assert response.json()["registrar"] == "GoDaddy"
    assert response.json()["auto_renew"] is False

    response = client.delete(f"/accounts/{account_id}/domains/{domain_id}", headers=auth_headers)
    assert response.status_code == 204
    assert client.get(f"/accounts/{account_id}/domains", headers=auth_headers).json() == []


def test_domain_requires_existing_account(client, auth_headers):
    response = client.post(
        "/accounts/does-not-exist/domains",
        json={"domain_name": "acme.test", "expiry_date": "2027-01-01", "registrar": "123-Reg"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_domain_from_another_login_user_returns_404(client, auth_headers, other_auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Owner's Client", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    domain_id = client.post(
        f"/accounts/{account_id}/domains",
        json={"domain_name": "acme.test", "expiry_date": "2027-01-01", "registrar": "123-Reg"},
        headers=auth_headers,
    ).json()["id"]

    # No GET-single route exists (list-only, matching the plan's minimal
    # surface) - exercise the list route instead, which should still 404
    # since the account itself doesn't exist under the other user's
    # organisation.
    response = client.get(f"/accounts/{account_id}/domains", headers=other_auth_headers)
    assert response.status_code == 404

    response = client.put(
        f"/accounts/{account_id}/domains/{domain_id}",
        json={"domain_name": "acme.test", "expiry_date": "2027-01-01", "registrar": "123-Reg"},
        headers=other_auth_headers,
    )
    assert response.status_code == 404

    response = client.delete(f"/accounts/{account_id}/domains/{domain_id}", headers=other_auth_headers)
    assert response.status_code == 404


def test_registrar_create_list_update_delete_flow(client, auth_headers):
    response = client.post(
        "/registrars", json={"name": "123-Reg", "notes": "https://123-reg.co.uk"}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    registrar_id = body["id"]
    assert body["name"] == "123-Reg"
    assert body["notes"] == "https://123-reg.co.uk"

    client.post("/registrars", json={"name": "GoDaddy"}, headers=auth_headers)

    response = client.get("/registrars", headers=auth_headers)
    assert response.status_code == 200
    # Alphabetical, not creation order (see models.Registrar).
    assert [r["name"] for r in response.json()] == ["123-Reg", "GoDaddy"]

    response = client.put(
        f"/registrars/{registrar_id}",
        json={"name": "123 Reg Ltd", "notes": None},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "123 Reg Ltd"
    assert response.json()["notes"] is None

    response = client.delete(f"/registrars/{registrar_id}", headers=auth_headers)
    assert response.status_code == 204
    assert [r["name"] for r in client.get("/registrars", headers=auth_headers).json()] == ["GoDaddy"]


def test_registrar_requires_non_blank_name(client, auth_headers):
    response = client.post("/registrars", json={"name": "   "}, headers=auth_headers)
    assert response.status_code == 422


def test_registrar_from_another_login_user_is_isolated(client, auth_headers, other_auth_headers):
    registrar_id = client.post("/registrars", json={"name": "123-Reg"}, headers=auth_headers).json()["id"]

    assert client.get("/registrars", headers=other_auth_headers).json() == []

    response = client.put(f"/registrars/{registrar_id}", json={"name": "GoDaddy"}, headers=other_auth_headers)
    assert response.status_code == 404

    response = client.delete(f"/registrars/{registrar_id}", headers=other_auth_headers)
    assert response.status_code == 404


def test_expense_attachment_upload_view_download_and_delete_flow(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    expense_id = client.post("/expenses", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.post(
        f"/expenses/{expense_id}/attachments",
        files={"file": ("receipt.pdf", b"%PDF-1.4 fake receipt", "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    attachment_id = body["id"]
    assert body["filename"] == "receipt.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size"] == len(b"%PDF-1.4 fake receipt")

    # Inlined on the parent expense, same as line_items - no separate list
    # call needed to see it.
    response = client.get(f"/expenses/{expense_id}", headers=auth_headers)
    assert [a["id"] for a in response.json()["attachments"]] == [attachment_id]

    response = client.get(f"/expenses/{expense_id}/attachments/{attachment_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake receipt"
    assert response.headers["content-type"] == "application/pdf"

    response = client.delete(f"/expenses/{expense_id}/attachments/{attachment_id}", headers=auth_headers)
    assert response.status_code == 204

    response = client.get(f"/expenses/{expense_id}", headers=auth_headers)
    assert response.json()["attachments"] == []

    response = client.get(f"/expenses/{expense_id}/attachments/{attachment_id}", headers=auth_headers)
    assert response.status_code == 404


def test_expense_attachment_upload_rejects_a_non_pdf(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    expense_id = client.post("/expenses", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.post(
        f"/expenses/{expense_id}/attachments",
        files={"file": ("receipt.png", b"not a pdf", "image/png")},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_expense_attachment_from_another_login_user_returns_404(client, auth_headers, other_auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Owner's Client", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    expense_id = client.post("/expenses", json={"account_id": account_id}, headers=auth_headers).json()["id"]
    attachment_id = client.post(
        f"/expenses/{expense_id}/attachments",
        files={"file": ("receipt.pdf", b"data", "application/pdf")},
        headers=auth_headers,
    ).json()["id"]

    response = client.get(f"/expenses/{expense_id}/attachments/{attachment_id}", headers=other_auth_headers)
    assert response.status_code == 404

    response = client.delete(
        f"/expenses/{expense_id}/attachments/{attachment_id}", headers=other_auth_headers
    )
    assert response.status_code == 404


def test_accounts_are_isolated_between_login_users(client, auth_headers, other_auth_headers):
    # Regression test: two different login users must not see each other's
    # accounts/quotes/invoices - see CLAUDE.md and models.py's Organisation
    # docstring. Each user gets their own auto-created Organisation on first
    # use.
    client.post(
        "/accounts",
        json={"business_name": "Owner's Client", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    )
    client.post(
        "/accounts",
        json={"business_name": "Other's Client", "email": "b@b.test", "address_line1": "2 High St"},
        headers=other_auth_headers,
    )

    owner_names = {a["business_name"] for a in client.get("/accounts", headers=auth_headers).json()["items"]}
    other_names = {
        a["business_name"] for a in client.get("/accounts", headers=other_auth_headers).json()["items"]
    }
    assert owner_names == {"Owner's Client"}
    assert other_names == {"Other's Client"}


def test_account_from_another_login_user_returns_404(client, auth_headers, other_auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Owner's Client", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]

    response = client.get(f"/accounts/{account_id}", headers=other_auth_headers)
    assert response.status_code == 404


def test_get_missing_account_returns_404(client, auth_headers):
    response = client.get("/accounts/999", headers=auth_headers)
    assert response.status_code == 404


def test_update_account_persists_and_is_returned_on_refetch(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]

    response = client.put(
        f"/accounts/{account_id}",
        json={
            "business_name": "Acme Ltd",
            "email": "b@b.test",
            "address_line1": "2 High St",
            "contact_name": "Jane Doe",
            "phone": "555-1234",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["business_name"] == "Acme Ltd"

    response = client.get(f"/accounts/{account_id}", headers=auth_headers)
    assert response.json()["business_name"] == "Acme Ltd"
    assert response.json()["contact_name"] == "Jane Doe"
    assert response.json()["phone"] == "555-1234"
    assert response.json()["address_line1"] == "2 High St"


def test_account_stores_the_full_structured_address(client, auth_headers):
    response = client.post(
        "/accounts",
        json={
            "business_name": "Acme",
            "email": "a@b.test",
            "address_line1": "1 Main St",
            "address_line2": "Suite 4",
            "town_or_city": "London",
            "county": "Greater London",
            "postcode": "SW1A 1AA",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["address_line1"] == "1 Main St"
    assert body["address_line2"] == "Suite 4"
    assert body["town_or_city"] == "London"
    assert body["county"] == "Greater London"
    assert body["postcode"] == "SW1A 1AA"


def test_account_address_line1_is_required(client, auth_headers):
    response = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "   "},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_missing_account_returns_404(client, auth_headers):
    response = client.put(
        "/accounts/999",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_update_account_without_a_name_returns_422(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]

    response = client.put(
        f"/accounts/{account_id}",
        json={"business_name": "", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_line_item_rejects_non_decimal_quantity(client, auth_headers):
    response = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
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


def test_line_item_applies_tax_rate_to_the_line_and_quote_totals(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "1", "unit_price": "100.00", "tax_rate": "0.20"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    item = response.json()["line_items"][0]
    assert item["tax_rate"] == "0.20"
    assert item["net_total"] == "100.00"
    assert item["tax_amount"] == "20.00"
    assert item["total"] == "120.00"
    assert response.json()["subtotal"] == "100.00"
    assert response.json()["tax_total"] == "20.00"
    assert response.json()["total"] == "120.00"


def test_line_item_tax_rate_defaults_to_zero(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )
    assert response.json()["line_items"][0]["tax_rate"] == "0"


def test_line_item_rejects_tax_rate_above_one(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "1", "unit_price": "100.00", "tax_rate": "1.5"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_sending_quote_with_no_line_items_returns_422(client, auth_headers):
    response = client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    )
    account_id = response.json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.post(f"/quotes/{quote_id}/send", headers=auth_headers)
    assert response.status_code == 422


def test_stats_requires_auth(client):
    response = client.get("/stats")
    assert response.status_code == 401


def test_stats_counts_accounts(client, auth_headers):
    response = client.get("/stats", headers=auth_headers)
    assert response.status_code == 200
    before = response.json()["account_count"]

    client.post(
        "/accounts",
        json={"business_name": "Acme", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    )

    response = client.get("/stats", headers=auth_headers)
    assert response.json()["account_count"] == before + 1


def test_stats_includes_quote_invoice_and_total_paid_fields(client, auth_headers):
    response = client.get("/stats", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["quote_count"] == 0
    assert body["invoice_count"] == 0
    assert body["quotes_sent_count"] == 0
    assert body["quotes_converted_count"] == 0
    assert body["total_paid"] == "0"
    assert body["currency"]  # the caller's reporting currency, defaulted if unset


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
    assert body["address_line1"] is None
    assert body["address_line2"] is None
    assert body["town_or_city"] is None
    assert body["county"] is None
    assert body["postcode"] is None
    assert body["payment_terms_days"] == 30
    assert body["quote_validity_days"] == 30
    assert body["currency"] == "GBP"
    assert body["utr"] is None
    assert body["vat_number"] is None
    assert body["bank_account_name"] is None
    assert body["bank_sort_code"] is None
    assert body["bank_account_number"] is None
    assert body["quote_document_header"] is None
    assert body["quote_document_footer"] is None
    assert body["invoice_document_header"] is None
    assert body["invoice_document_footer"] is None
    assert body["expense_document_header"] is None
    assert body["expense_document_footer"] is None
    assert body["accent_color"] is None


def test_saving_business_profile_persists_and_is_returned_on_refetch(client, auth_headers):
    response = client.put(
        "/settings/business-profile",
        json={
            "title": "Dr",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "business_name": "Acme Consulting",
            "address_line1": "1 Main St",
            "address_line2": "Suite 4",
            "town_or_city": "London",
            "county": "Greater London",
            "postcode": "SW1A 1AA",
            "payment_terms_days": 14,
            "currency": "usd",
            "utr": "1234567890",
            "vat_number": "GB123456789",
            "bank_account_name": "Acme Consulting Ltd",
            "bank_sort_code": "12-34-56",
            "bank_account_number": "12345678",
            "quote_document_header": "Acme Consulting",
            "quote_document_footer": "Valid for 30 days.",
            "invoice_document_header": "Acme Consulting\nCompany no. 12345678",
            "invoice_document_footer": "Thank you for your business!",
            "expense_document_header": "Acme Consulting",
            "expense_document_footer": "Internal use only.",
            "accent_color": "#2563EB",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["business_name"] == "Acme Consulting"
    assert response.json()["payment_terms_days"] == 14
    assert response.json()["currency"] == "USD"

    response = client.get("/settings/business-profile", headers=auth_headers)
    assert response.json()["title"] == "Dr"
    assert response.json()["first_name"] == "Ada"
    assert response.json()["address_line1"] == "1 Main St"
    assert response.json()["town_or_city"] == "London"
    assert response.json()["postcode"] == "SW1A 1AA"
    assert response.json()["currency"] == "USD"
    assert response.json()["utr"] == "1234567890"
    assert response.json()["vat_number"] == "GB123456789"
    assert response.json()["bank_account_name"] == "Acme Consulting Ltd"
    assert response.json()["bank_sort_code"] == "12-34-56"
    assert response.json()["bank_account_number"] == "12345678"
    assert response.json()["quote_document_header"] == "Acme Consulting"
    assert response.json()["quote_document_footer"] == "Valid for 30 days."
    assert response.json()["invoice_document_header"] == "Acme Consulting\nCompany no. 12345678"
    assert response.json()["invoice_document_footer"] == "Thank you for your business!"
    assert response.json()["expense_document_header"] == "Acme Consulting"
    assert response.json()["expense_document_footer"] == "Internal use only."
    assert response.json()["accent_color"] == "#2563EB"


def test_address_fields_are_optional(client, auth_headers):
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
    assert response.json()["address_line1"] is None
    assert response.json()["postcode"] is None
    assert response.json()["bank_account_name"] is None
    assert response.json()["quote_document_header"] is None
    assert response.json()["invoice_document_header"] is None
    assert response.json()["expense_document_header"] is None


def test_blank_bank_and_document_fields_are_normalised_to_null(client, auth_headers):
    response = client.put(
        "/settings/business-profile",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "business_name": "Acme Consulting",
            "payment_terms_days": 30,
            "bank_account_name": "   ",
            "quote_document_header": "   ",
            "invoice_document_header": "   ",
            "expense_document_header": "   ",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["bank_account_name"] is None
    assert response.json()["quote_document_header"] is None
    assert response.json()["invoice_document_header"] is None
    assert response.json()["expense_document_header"] is None


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


def test_saving_business_profile_with_a_malformed_accent_color_returns_422(client, auth_headers):
    response = client.put(
        "/settings/business-profile",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "business_name": "Acme",
            "payment_terms_days": 30,
            "accent_color": "not-a-color",
        },
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
        json={"business_name": "Client Co", "email": "a@b.test", "address_line1": "1 Main St"},
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
        json={"business_name": "Client Co", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]

    response = client.get(f"/quotes/{quote_id}/pdf", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def _send_invoice(client, auth_headers, *, currency=None):
    body = {"business_name": "Client Co", "email": "a@b.test", "address_line1": "1 Main St"}
    account_id = client.post("/accounts", json=body, headers=auth_headers).json()["id"]
    quote_body = {"account_id": account_id, **({"currency": currency} if currency else {})}
    quote_id = client.post("/quotes", json=quote_body, headers=auth_headers).json()["id"]
    client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )
    client.post(f"/quotes/{quote_id}/send", headers=auth_headers)
    invoice_id = client.post(f"/quotes/{quote_id}/convert", headers=auth_headers).json()["id"]
    return client.post(f"/invoices/{invoice_id}/send", headers=auth_headers).json()


def test_pay_invoice_marks_it_paid(client, auth_headers):
    invoice = _send_invoice(client, auth_headers)
    response = client.post(f"/invoices/{invoice['id']}/pay", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "paid"


def test_cannot_pay_a_draft_invoice(client, auth_headers):
    account_id = client.post(
        "/accounts",
        json={"business_name": "Client Co", "email": "a@b.test", "address_line1": "1 Main St"},
        headers=auth_headers,
    ).json()["id"]
    quote_id = client.post("/quotes", json={"account_id": account_id}, headers=auth_headers).json()["id"]
    client.post(
        f"/quotes/{quote_id}/line-items",
        json={"description": "Work", "quantity": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )
    client.post(f"/quotes/{quote_id}/send", headers=auth_headers)
    invoice_id = client.post(f"/quotes/{quote_id}/convert", headers=auth_headers).json()["id"]

    response = client.post(f"/invoices/{invoice_id}/pay", headers=auth_headers)
    assert response.status_code == 409


def test_monthly_totals_requires_auth(client):
    response = client.get("/invoices/monthly-totals")
    assert response.status_code == 401


def test_monthly_totals_reports_the_profile_currency_and_twelve_months(client, auth_headers):
    client.put(
        "/settings/business-profile",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "business_name": "Acme Consulting",
            "payment_terms_days": 30,
            "currency": "USD",
        },
        headers=auth_headers,
    )
    invoice = _send_invoice(client, auth_headers, currency="USD")
    client.post(f"/invoices/{invoice['id']}/pay", headers=auth_headers)

    response = client.get("/invoices/monthly-totals", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "USD"
    assert len(body["months"]) == 12

    current_month = invoice["issue_date"][:7]
    entry = next(m for m in body["months"] if m["month"] == current_month)
    assert entry["paid_total"] == "100.00"
    assert entry["unpaid_total"] == "0"


def test_monthly_totals_excludes_invoices_in_a_different_currency(client, auth_headers):
    # Profile defaults to GBP; this invoice is USD, so it shouldn't count.
    invoice = _send_invoice(client, auth_headers, currency="USD")

    response = client.get("/invoices/monthly-totals", headers=auth_headers)
    current_month = invoice["issue_date"][:7]
    entry = next(m for m in response.json()["months"] if m["month"] == current_month)
    assert entry["paid_total"] == "0"
    assert entry["unpaid_total"] == "0"


def _create_expense(client, auth_headers, *, currency=None):
    body = {"business_name": "Client Co", "email": "a@b.test", "address_line1": "1 Main St"}
    account_id = client.post("/accounts", json=body, headers=auth_headers).json()["id"]
    expense_body = {"account_id": account_id, **({"currency": currency} if currency else {})}
    expense = client.post("/expenses", json=expense_body, headers=auth_headers).json()
    client.post(
        f"/expenses/{expense['id']}/line-items",
        json={"description": "Domain renewal", "quantity": "1", "unit_price": "12.00"},
        headers=auth_headers,
    )
    return client.get(f"/expenses/{expense['id']}", headers=auth_headers).json()


def test_expense_monthly_totals_requires_auth(client):
    response = client.get("/expenses/monthly-totals")
    assert response.status_code == 401


def test_expense_monthly_totals_reports_the_profile_currency_and_twelve_months(client, auth_headers):
    client.put(
        "/settings/business-profile",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "business_name": "Acme Consulting",
            "payment_terms_days": 30,
            "currency": "USD",
        },
        headers=auth_headers,
    )
    expense = _create_expense(client, auth_headers, currency="USD")

    response = client.get("/expenses/monthly-totals", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "USD"
    assert len(body["months"]) == 12

    current_month = expense["issue_date"][:7]
    entry = next(m for m in body["months"] if m["month"] == current_month)
    assert entry["total"] == "12.00"


def test_expense_monthly_totals_excludes_expenses_in_a_different_currency(client, auth_headers):
    # Profile defaults to GBP; this expense is USD, so it shouldn't count.
    expense = _create_expense(client, auth_headers, currency="USD")

    response = client.get("/expenses/monthly-totals", headers=auth_headers)
    current_month = expense["issue_date"][:7]
    entry = next(m for m in response.json()["months"] if m["month"] == current_month)
    assert entry["total"] == "0"
