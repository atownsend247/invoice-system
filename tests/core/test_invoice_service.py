from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from invoice_system.errors import InvalidTransition, NotFound, ValidationFailed
from invoice_system.models import Invoice, InvoiceStatus


@pytest.fixture
def account(application):
    return application.accounts.create_account(
        business_name="Acme Co", email="jane@acme.test", address="1 Main St"
    )


@pytest.fixture
def draft_invoice(application, account):
    quote = application.quotes.create_quote(account_id=account.id)
    quote = application.quotes.add_line_item(
        quote.id, description="Work", quantity=Decimal("2"), unit_price=Decimal("100.00")
    )
    quote = application.quotes.send(quote.id)
    return application.quotes.convert_to_invoice(quote.id)


def test_get_missing_invoice_raises_not_found(application):
    with pytest.raises(NotFound):
        application.invoices.get_invoice(999)


def test_send_invoice_assigns_number_sets_due_date_and_freezes(application, draft_invoice, fake_clock):
    invoice = application.invoices.send(draft_invoice.id)

    assert invoice.status == InvoiceStatus.SENT
    assert invoice.number == "INV-0001"
    assert invoice.due_date == fake_clock().date() + timedelta(days=30)

    with pytest.raises(InvalidTransition):
        application.invoices.add_line_item(
            invoice.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1")
        )


def test_send_invoice_uses_payment_terms_days_when_given(application, draft_invoice, fake_clock):
    invoice = application.invoices.send(draft_invoice.id, payment_terms_days=5)
    assert invoice.due_date == fake_clock().date() + timedelta(days=5)


def test_send_invoice_falls_back_to_the_default_when_payment_terms_not_given(
    application, draft_invoice, fake_clock
):
    invoice = application.invoices.send(draft_invoice.id, payment_terms_days=None)
    assert invoice.due_date == fake_clock().date() + timedelta(days=30)


def test_cannot_send_invoice_without_line_items(application, account, fake_clock):
    # Invoices are normally only created via quote conversion, which always
    # copies at least one item - go through the repository directly to reach
    # the otherwise-unreachable zero-item state.
    empty = application.repository.create_invoice(
        Invoice(
            id=None,
            account_id=account.id,
            quote_id=None,
            number=None,
            status=InvoiceStatus.DRAFT,
            currency="USD",
            issue_date=fake_clock().date(),
            due_date=None,
            created_at=fake_clock(),
        )
    )

    with pytest.raises(ValidationFailed):
        application.invoices.send(empty.id)


def test_void_invoice(application, draft_invoice):
    voided = application.invoices.void(draft_invoice.id)
    assert voided.status == InvoiceStatus.VOID


def test_cannot_void_paid_invoice(application, draft_invoice):
    invoice = application.invoices.send(draft_invoice.id)
    invoice.status = InvoiceStatus.PAID
    application.repository.update_invoice(invoice)

    with pytest.raises(InvalidTransition):
        application.invoices.void(invoice.id)


def test_pay_marks_a_sent_invoice_paid(application, draft_invoice):
    sent = application.invoices.send(draft_invoice.id)
    paid = application.invoices.pay(sent.id)
    assert paid.status == InvoiceStatus.PAID


def test_cannot_pay_a_draft_invoice(application, draft_invoice):
    with pytest.raises(InvalidTransition):
        application.invoices.pay(draft_invoice.id)


def test_cannot_pay_an_already_paid_invoice(application, draft_invoice):
    sent = application.invoices.send(draft_invoice.id)
    application.invoices.pay(sent.id)

    with pytest.raises(InvalidTransition):
        application.invoices.pay(sent.id)


def test_cannot_pay_a_void_invoice(application, draft_invoice):
    sent = application.invoices.send(draft_invoice.id)
    application.invoices.void(sent.id)

    with pytest.raises(InvalidTransition):
        application.invoices.pay(sent.id)


def test_get_missing_invoice_raises_not_found_for_pay(application):
    with pytest.raises(NotFound):
        application.invoices.pay(999)


class TestMonthlyTotals:
    """InvoiceService.monthly_totals - see the docstring on the method
    itself for what's included/excluded and why."""

    def _create_invoice(self, application, account, *, currency="GBP", price="100.00"):
        quote = application.quotes.create_quote(account_id=account.id, currency=currency)
        quote = application.quotes.add_line_item(
            quote.id, description="Work", quantity=Decimal("1"), unit_price=Decimal(price)
        )
        quote = application.quotes.send(quote.id)
        return application.quotes.convert_to_invoice(quote.id)

    def test_returns_twelve_months_ending_with_the_current_one_even_with_no_data(
        self, application, fake_clock
    ):
        fake_clock.set(datetime(2026, 6, 15, tzinfo=UTC))
        totals = application.invoices.monthly_totals("GBP")
        assert [t.month for t in totals] == [
            "2025-07",
            "2025-08",
            "2025-09",
            "2025-10",
            "2025-11",
            "2025-12",
            "2026-01",
            "2026-02",
            "2026-03",
            "2026-04",
            "2026-05",
            "2026-06",
        ]
        assert all(t.paid_total == Decimal("0") and t.unpaid_total == Decimal("0") for t in totals)

    def test_buckets_by_issue_date_month_split_paid_vs_unpaid(self, application, account, fake_clock):
        fake_clock.set(datetime(2026, 3, 10, tzinfo=UTC))
        sent = application.invoices.send(self._create_invoice(application, account, price="100.00").id)
        application.invoices.pay(sent.id)

        fake_clock.set(datetime(2026, 3, 20, tzinfo=UTC))
        application.invoices.send(self._create_invoice(application, account, price="50.00").id)

        totals = {t.month: t for t in application.invoices.monthly_totals("GBP")}
        assert totals["2026-03"].paid_total == Decimal("100.00")
        assert totals["2026-03"].unpaid_total == Decimal("50.00")

    def test_draft_and_void_invoices_are_excluded(self, application, account, fake_clock):
        fake_clock.set(datetime(2026, 3, 10, tzinfo=UTC))
        self._create_invoice(application, account, price="100.00")  # left as draft
        sent = application.invoices.send(self._create_invoice(application, account, price="75.00").id)
        application.invoices.void(sent.id)

        totals = {t.month: t for t in application.invoices.monthly_totals("GBP")}
        assert totals["2026-03"].paid_total == Decimal("0")
        assert totals["2026-03"].unpaid_total == Decimal("0")

    def test_invoices_outside_the_window_are_excluded(self, application, account, fake_clock):
        fake_clock.set(datetime(2025, 1, 10, tzinfo=UTC))
        application.invoices.send(self._create_invoice(application, account, price="100.00").id)

        fake_clock.set(datetime(2026, 6, 1, tzinfo=UTC))
        totals = application.invoices.monthly_totals("GBP")
        assert all(t.paid_total == Decimal("0") and t.unpaid_total == Decimal("0") for t in totals)

    def test_invoices_in_a_different_currency_are_excluded(self, application, account, fake_clock):
        fake_clock.set(datetime(2026, 3, 10, tzinfo=UTC))
        invoice = self._create_invoice(application, account, currency="USD", price="100.00")
        application.invoices.send(invoice.id)

        totals = {t.month: t for t in application.invoices.monthly_totals("GBP")}
        assert totals["2026-03"].paid_total == Decimal("0")
        assert totals["2026-03"].unpaid_total == Decimal("0")

    def test_january_rolls_back_to_december_of_the_previous_year(self, application, fake_clock):
        fake_clock.set(datetime(2026, 1, 1, tzinfo=UTC))
        totals = application.invoices.monthly_totals("GBP")
        assert totals[0].month == "2025-02"
        assert totals[-1].month == "2026-01"

    @pytest.fixture
    def account(self, application):
        return application.accounts.create_account(
            business_name="Acme Co", email="jane@acme.test", address="1 Main St"
        )
