from datetime import UTC, datetime

import pytest

from invoice_system.auth import build_auth
from invoice_system.demo_data import DEMO_CURRENCY, DEMO_EMAIL, DEMO_PASSWORD, seed_demo_data
from invoice_system.factory import build_application

FIXED_NOW = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)


@pytest.fixture
def application(tmp_path):
    app = build_application(tmp_path / "test.db")
    yield app
    app.close()


@pytest.fixture
def auth(tmp_path):
    ctx = build_auth(tmp_path / "auth.db")
    yield ctx
    ctx.close()


def test_seed_demo_data_creates_a_demo_login_user(application, auth):
    seeded = seed_demo_data(application, auth, now=FIXED_NOW)
    assert seeded is True

    login = auth.service.login(DEMO_EMAIL, DEMO_PASSWORD)
    assert login.user.email == DEMO_EMAIL


def test_seed_demo_data_creates_a_business_profile_in_the_demo_currency(application, auth):
    seed_demo_data(application, auth, now=FIXED_NOW)
    login = auth.service.login(DEMO_EMAIL, DEMO_PASSWORD)

    profile = application.business_profiles.get_profile(login.user.id)
    assert profile.business_name
    assert profile.currency == DEMO_CURRENCY


def test_seed_demo_data_creates_multiple_accounts(application, auth):
    seed_demo_data(application, auth, now=FIXED_NOW)
    assert application.stats.get_stats().account_count >= 3


def test_seed_demo_data_spans_a_mix_of_quote_and_invoice_statuses(application, auth):
    seed_demo_data(application, auth, now=FIXED_NOW)

    quote_statuses = {q.status.value for q in application.quotes.list_quotes()}
    invoice_statuses = {i.status.value for i in application.invoices.list_invoices()}

    # Not asserting the exact set - just that it's not a single-status pile,
    # which is the whole point of "various states and combinations".
    assert len(quote_statuses) >= 3
    assert len(invoice_statuses) >= 3


def test_seed_demo_data_produces_both_an_overdue_and_an_outstanding_invoice(application, auth):
    seed_demo_data(application, auth, now=FIXED_NOW)
    today = FIXED_NOW.date()

    sent = [i for i in application.invoices.list_invoices() if i.status.value == "sent"]
    assert any(i.due_date and i.due_date < today for i in sent), "expected at least one overdue invoice"
    assert any(i.due_date and i.due_date >= today for i in sent), "expected at least one outstanding invoice"


def test_seed_demo_data_produces_at_least_one_paid_invoice(application, auth):
    seed_demo_data(application, auth, now=FIXED_NOW)
    assert any(i.status.value == "paid" for i in application.invoices.list_invoices())


def test_seed_demo_data_every_line_item_is_in_the_demo_currency(application, auth):
    seed_demo_data(application, auth, now=FIXED_NOW)
    assert all(q.currency == DEMO_CURRENCY for q in application.quotes.list_quotes())
    assert all(i.currency == DEMO_CURRENCY for i in application.invoices.list_invoices())


def test_seed_demo_data_uses_more_than_one_vat_rate(application, auth):
    seed_demo_data(application, auth, now=FIXED_NOW)
    rates = {item.tax_rate for q in application.quotes.list_quotes() for item in q.line_items}
    assert len(rates) >= 2


def test_seed_demo_data_is_idempotent(application, auth):
    first = seed_demo_data(application, auth, now=FIXED_NOW)
    accounts_after_first = application.stats.get_stats().account_count

    second = seed_demo_data(application, auth, now=FIXED_NOW)

    assert first is True
    assert second is False
    assert application.stats.get_stats().account_count == accounts_after_first
