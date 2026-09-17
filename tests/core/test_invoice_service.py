from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from invoice_system.errors import InvalidTransition, NotFound, ValidationFailed
from invoice_system.ids import new_id
from invoice_system.models import Invoice, InvoiceStatus


@pytest.fixture
def account(application, organisation_id):
    return application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="jane@acme.test",
        address_line1="1 Main St",
    )


@pytest.fixture
def draft_invoice(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id, quote.id, description="Work", quantity=Decimal("2"), unit_price=Decimal("100.00")
    )
    quote = application.quotes.send(organisation_id, quote.id)
    return application.quotes.convert_to_invoice(organisation_id, quote.id)


def test_get_missing_invoice_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.invoices.get_invoice(organisation_id, 999)


def test_list_invoices_filters_by_account_name_and_status_and_paginates(
    application, organisation_id, draft_invoice
):
    northwind = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Northwind Traders",
        email="a@northwind.test",
        address_line1="2 Kings Road",
    )
    other_quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=northwind.id)
    other_quote = application.quotes.add_line_item(
        organisation_id,
        other_quote.id,
        description="Work",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
    )
    other_quote = application.quotes.send(organisation_id, other_quote.id)
    other_invoice = application.quotes.convert_to_invoice(organisation_id, other_quote.id)

    by_account_name = application.invoices.list_invoices(organisation_id, account_name="northwind").items
    assert [i.id for i in by_account_name] == [other_invoice.id]

    by_status = application.invoices.list_invoices(organisation_id, status=InvoiceStatus.DRAFT).items
    assert {i.id for i in by_status} == {draft_invoice.id, other_invoice.id}

    page = application.invoices.list_invoices(organisation_id, page=1, page_size=1)
    assert len(page.items) == 1
    assert page.total == 2


@pytest.mark.parametrize(("page", "page_size"), [(0, 20), (1, 0), (1, 201)])
def test_list_invoices_rejects_invalid_pagination(application, organisation_id, page, page_size):
    with pytest.raises(ValidationFailed):
        application.invoices.list_invoices(organisation_id, page=page, page_size=page_size)


def test_invoice_from_another_organisation_raises_not_found(application, organisation_id, draft_invoice):
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.invoices.get_invoice(other_organisation_id, draft_invoice.id)


def test_send_invoice_assigns_number_sets_due_date_and_freezes(
    application, organisation_id, draft_invoice, fake_clock
):
    invoice = application.invoices.send(organisation_id, draft_invoice.id)

    assert invoice.status == InvoiceStatus.SENT
    assert invoice.number == "INV-0001"
    assert invoice.due_date == fake_clock().date() + timedelta(days=30)

    with pytest.raises(InvalidTransition):
        application.invoices.add_line_item(
            organisation_id, invoice.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1")
        )


def test_send_invoice_uses_payment_terms_days_when_given(
    application, organisation_id, draft_invoice, fake_clock
):
    invoice = application.invoices.send(organisation_id, draft_invoice.id, payment_terms_days=5)
    assert invoice.due_date == fake_clock().date() + timedelta(days=5)


def test_send_invoice_falls_back_to_the_default_when_payment_terms_not_given(
    application, organisation_id, draft_invoice, fake_clock
):
    invoice = application.invoices.send(organisation_id, draft_invoice.id, payment_terms_days=None)
    assert invoice.due_date == fake_clock().date() + timedelta(days=30)


def test_cannot_send_invoice_without_line_items(application, organisation_id, account, fake_clock):
    # Invoices are normally only created via quote conversion, which always
    # copies at least one item - go through the repository directly to reach
    # the otherwise-unreachable zero-item state.
    empty = application.repository.create_invoice(
        Invoice(
            id=new_id(),
            organisation_id=organisation_id,
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
        application.invoices.send(organisation_id, empty.id)


def test_void_invoice(application, organisation_id, draft_invoice):
    voided = application.invoices.void(organisation_id, draft_invoice.id)
    assert voided.status == InvoiceStatus.VOID


def test_cannot_void_paid_invoice(application, organisation_id, draft_invoice):
    invoice = application.invoices.send(organisation_id, draft_invoice.id)
    invoice.status = InvoiceStatus.PAID
    application.repository.update_invoice(invoice)

    with pytest.raises(InvalidTransition):
        application.invoices.void(organisation_id, invoice.id)


def test_pay_marks_a_sent_invoice_paid(application, organisation_id, draft_invoice):
    sent = application.invoices.send(organisation_id, draft_invoice.id)
    paid = application.invoices.pay(organisation_id, sent.id)
    assert paid.status == InvoiceStatus.PAID


def test_cannot_pay_a_draft_invoice(application, organisation_id, draft_invoice):
    with pytest.raises(InvalidTransition):
        application.invoices.pay(organisation_id, draft_invoice.id)


def test_cannot_pay_an_already_paid_invoice(application, organisation_id, draft_invoice):
    sent = application.invoices.send(organisation_id, draft_invoice.id)
    application.invoices.pay(organisation_id, sent.id)

    with pytest.raises(InvalidTransition):
        application.invoices.pay(organisation_id, sent.id)


def test_cannot_pay_a_void_invoice(application, organisation_id, draft_invoice):
    sent = application.invoices.send(organisation_id, draft_invoice.id)
    application.invoices.void(organisation_id, sent.id)

    with pytest.raises(InvalidTransition):
        application.invoices.pay(organisation_id, sent.id)


def test_get_missing_invoice_raises_not_found_for_pay(application, organisation_id):
    with pytest.raises(NotFound):
        application.invoices.pay(organisation_id, 999)


def test_add_line_item_to_a_draft_invoice_applies_tax_rate(application, organisation_id, account, fake_clock):
    empty = application.repository.create_invoice(
        Invoice(
            id=new_id(),
            organisation_id=organisation_id,
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
    invoice = application.invoices.add_line_item(
        organisation_id,
        empty.id,
        description="Work",
        quantity=Decimal("2"),
        unit_price=Decimal("100.00"),
        tax_rate=Decimal("0.20"),
    )
    assert invoice.subtotal == Decimal("200.00")
    assert invoice.tax_total == Decimal("40.00")
    assert invoice.total == Decimal("240.00")


class TestMonthlyTotals:
    """InvoiceService.monthly_totals - see the docstring on the method
    itself for what's included/excluded and why."""

    def _create_invoice(self, application, organisation_id, account, *, currency="GBP", price="100.00"):
        quote = application.quotes.create_quote(
            organisation_id=organisation_id, account_id=account.id, currency=currency
        )
        quote = application.quotes.add_line_item(
            organisation_id, quote.id, description="Work", quantity=Decimal("1"), unit_price=Decimal(price)
        )
        quote = application.quotes.send(organisation_id, quote.id)
        return application.quotes.convert_to_invoice(organisation_id, quote.id)

    def test_returns_twelve_months_ending_with_the_current_one_even_with_no_data(
        self, application, organisation_id, fake_clock
    ):
        fake_clock.set(datetime(2026, 6, 15, tzinfo=UTC))
        totals = application.invoices.monthly_totals(organisation_id, "GBP")
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

    def test_buckets_by_issue_date_month_split_paid_vs_unpaid(
        self, application, organisation_id, account, fake_clock
    ):
        fake_clock.set(datetime(2026, 3, 10, tzinfo=UTC))
        sent = application.invoices.send(
            organisation_id, self._create_invoice(application, organisation_id, account, price="100.00").id
        )
        application.invoices.pay(organisation_id, sent.id)

        fake_clock.set(datetime(2026, 3, 20, tzinfo=UTC))
        application.invoices.send(
            organisation_id, self._create_invoice(application, organisation_id, account, price="50.00").id
        )

        totals = {t.month: t for t in application.invoices.monthly_totals(organisation_id, "GBP")}
        assert totals["2026-03"].paid_total == Decimal("100.00")
        assert totals["2026-03"].unpaid_total == Decimal("50.00")

    def test_draft_and_void_invoices_are_excluded(self, application, organisation_id, account, fake_clock):
        fake_clock.set(datetime(2026, 3, 10, tzinfo=UTC))
        self._create_invoice(application, organisation_id, account, price="100.00")  # left as draft
        sent = application.invoices.send(
            organisation_id, self._create_invoice(application, organisation_id, account, price="75.00").id
        )
        application.invoices.void(organisation_id, sent.id)

        totals = {t.month: t for t in application.invoices.monthly_totals(organisation_id, "GBP")}
        assert totals["2026-03"].paid_total == Decimal("0")
        assert totals["2026-03"].unpaid_total == Decimal("0")

    def test_invoices_outside_the_window_are_excluded(
        self, application, organisation_id, account, fake_clock
    ):
        fake_clock.set(datetime(2025, 1, 10, tzinfo=UTC))
        application.invoices.send(
            organisation_id, self._create_invoice(application, organisation_id, account, price="100.00").id
        )

        fake_clock.set(datetime(2026, 6, 1, tzinfo=UTC))
        totals = application.invoices.monthly_totals(organisation_id, "GBP")
        assert all(t.paid_total == Decimal("0") and t.unpaid_total == Decimal("0") for t in totals)

    def test_invoices_in_a_different_currency_are_excluded(
        self, application, organisation_id, account, fake_clock
    ):
        fake_clock.set(datetime(2026, 3, 10, tzinfo=UTC))
        invoice = self._create_invoice(application, organisation_id, account, currency="USD", price="100.00")
        application.invoices.send(organisation_id, invoice.id)

        totals = {t.month: t for t in application.invoices.monthly_totals(organisation_id, "GBP")}
        assert totals["2026-03"].paid_total == Decimal("0")
        assert totals["2026-03"].unpaid_total == Decimal("0")

    def test_invoices_from_another_organisation_are_excluded(
        self, application, organisation_id, account, fake_clock
    ):
        fake_clock.set(datetime(2026, 3, 10, tzinfo=UTC))
        application.invoices.send(
            organisation_id, self._create_invoice(application, organisation_id, account, price="100.00").id
        )

        other_organisation_id = application.organisations.get_or_create_for_user("user-2")
        totals = {t.month: t for t in application.invoices.monthly_totals(other_organisation_id, "GBP")}
        assert totals["2026-03"].paid_total == Decimal("0")
        assert totals["2026-03"].unpaid_total == Decimal("0")

    def test_january_rolls_back_to_december_of_the_previous_year(
        self, application, organisation_id, fake_clock
    ):
        fake_clock.set(datetime(2026, 1, 1, tzinfo=UTC))
        totals = application.invoices.monthly_totals(organisation_id, "GBP")
        assert totals[0].month == "2025-02"
        assert totals[-1].month == "2026-01"

    @pytest.fixture
    def account(self, application, organisation_id):
        return application.accounts.create_account(
            organisation_id=organisation_id,
            business_name="Acme Co",
            email="jane@acme.test",
            address_line1="1 Main St",
        )
