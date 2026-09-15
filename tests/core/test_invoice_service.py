from datetime import timedelta
from decimal import Decimal

import pytest

from invoice_system.errors import InvalidTransition, NotFound, ValidationFailed
from invoice_system.models import Invoice, InvoiceStatus


@pytest.fixture
def account(application):
    return application.accounts.create_account(business_name="Acme Co", email="jane@acme.test", address="1 Main St")


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
        application.invoices.add_line_item(invoice.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1"))


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
