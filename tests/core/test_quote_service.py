from decimal import Decimal

import pytest

from invoice_system.errors import InvalidTransition, NotFound, ValidationFailed
from invoice_system.models import QuoteStatus


@pytest.fixture
def account(application):
    return application.accounts.create_account(business_name="Acme Co", email="jane@acme.test", address="1 Main St")


def test_create_quote_requires_existing_account(application):
    with pytest.raises(NotFound):
        application.quotes.create_quote(account_id=999)


def test_quote_lifecycle_through_conversion_to_invoice(application, account):
    quote = application.quotes.create_quote(account_id=account.id)
    assert quote.status == QuoteStatus.DRAFT
    assert quote.number is None

    quote = application.quotes.add_line_item(
        quote.id, description="Design work", quantity=Decimal("10"), unit_price=Decimal("50.00")
    )
    assert quote.total == Decimal("500.00")

    quote = application.quotes.send(quote.id)
    assert quote.status == QuoteStatus.SENT
    assert quote.number == "Q-0001"

    invoice = application.quotes.convert_to_invoice(quote.id)
    assert invoice.account_id == account.id
    assert invoice.quote_id == quote.id
    assert invoice.status.value == "draft"
    assert invoice.total == Decimal("500.00")
    assert [item.description for item in invoice.line_items] == ["Design work"]

    converted_quote = application.quotes.get_quote(quote.id)
    assert converted_quote.status == QuoteStatus.CONVERTED


def test_cannot_send_quote_without_line_items(application, account):
    quote = application.quotes.create_quote(account_id=account.id)
    with pytest.raises(ValidationFailed):
        application.quotes.send(quote.id)


def test_cannot_add_line_item_to_sent_quote(application, account):
    quote = application.quotes.create_quote(account_id=account.id)
    quote = application.quotes.add_line_item(quote.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1"))
    quote = application.quotes.send(quote.id)

    with pytest.raises(InvalidTransition):
        application.quotes.add_line_item(quote.id, description="y", quantity=Decimal("1"), unit_price=Decimal("1"))


def test_cannot_convert_draft_quote(application, account):
    quote = application.quotes.create_quote(account_id=account.id)
    with pytest.raises(InvalidTransition):
        application.quotes.convert_to_invoice(quote.id)


def test_cannot_convert_quote_twice(application, account):
    quote = application.quotes.create_quote(account_id=account.id)
    quote = application.quotes.add_line_item(quote.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1"))
    quote = application.quotes.send(quote.id)
    application.quotes.convert_to_invoice(quote.id)

    with pytest.raises(InvalidTransition):
        application.quotes.convert_to_invoice(quote.id)


def test_quote_numbers_increment_independently_of_invoice_numbers(application, account):
    first = application.quotes.create_quote(account_id=account.id)
    first = application.quotes.add_line_item(first.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1"))
    first = application.quotes.send(first.id)
    second = application.quotes.create_quote(account_id=account.id)
    second = application.quotes.add_line_item(second.id, description="y", quantity=Decimal("1"), unit_price=Decimal("1"))
    second = application.quotes.send(second.id)

    assert first.number == "Q-0001"
    assert second.number == "Q-0002"
