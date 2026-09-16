from decimal import Decimal

import pytest

from invoice_system.errors import InvalidTransition, NotFound, ValidationFailed
from invoice_system.models import QuoteStatus


@pytest.fixture
def account(application, organisation_id):
    return application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="jane@acme.test",
        address_line1="1 Main St",
    )


def test_create_quote_requires_existing_account(application, organisation_id):
    with pytest.raises(NotFound):
        application.quotes.create_quote(organisation_id=organisation_id, account_id=999)


def test_create_quote_requires_account_in_same_organisation(application, organisation_id, account):
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.quotes.create_quote(organisation_id=other_organisation_id, account_id=account.id)


def test_quote_lifecycle_through_conversion_to_invoice(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    assert quote.status == QuoteStatus.DRAFT
    assert quote.number is None

    quote = application.quotes.add_line_item(
        organisation_id,
        quote.id,
        description="Design work",
        quantity=Decimal("10"),
        unit_price=Decimal("50.00"),
    )
    assert quote.total == Decimal("500.00")

    quote = application.quotes.send(organisation_id, quote.id)
    assert quote.status == QuoteStatus.SENT
    assert quote.number == "Q-0001"

    invoice = application.quotes.convert_to_invoice(organisation_id, quote.id)
    assert invoice.account_id == account.id
    assert invoice.quote_id == quote.id
    assert invoice.status.value == "draft"
    assert invoice.total == Decimal("500.00")
    assert [item.description for item in invoice.line_items] == ["Design work"]

    converted_quote = application.quotes.get_quote(organisation_id, quote.id)
    assert converted_quote.status == QuoteStatus.CONVERTED


def test_cannot_send_quote_without_line_items(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    with pytest.raises(ValidationFailed):
        application.quotes.send(organisation_id, quote.id)


def test_cannot_add_line_item_to_sent_quote(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id, quote.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1")
    )
    quote = application.quotes.send(organisation_id, quote.id)

    with pytest.raises(InvalidTransition):
        application.quotes.add_line_item(
            organisation_id, quote.id, description="y", quantity=Decimal("1"), unit_price=Decimal("1")
        )


def test_cannot_convert_draft_quote(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    with pytest.raises(InvalidTransition):
        application.quotes.convert_to_invoice(organisation_id, quote.id)


def test_cannot_convert_quote_twice(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id, quote.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1")
    )
    quote = application.quotes.send(organisation_id, quote.id)
    application.quotes.convert_to_invoice(organisation_id, quote.id)

    with pytest.raises(InvalidTransition):
        application.quotes.convert_to_invoice(organisation_id, quote.id)


def test_quote_from_another_organisation_raises_not_found(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")

    with pytest.raises(NotFound):
        application.quotes.get_quote(other_organisation_id, quote.id)


def test_line_item_tax_defaults_to_zero_and_total_is_net(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id,
        quote.id,
        description="Design work",
        quantity=Decimal("10"),
        unit_price=Decimal("50.00"),
    )
    item = quote.line_items[0]
    assert item.tax_rate == Decimal("0")
    assert item.net_total == Decimal("500.00")
    assert item.tax_amount == Decimal("0")
    assert item.total == Decimal("500.00")
    assert quote.subtotal == Decimal("500.00")
    assert quote.tax_total == Decimal("0")
    assert quote.total == Decimal("500.00")


def test_line_item_tax_rate_is_applied_to_the_line_and_the_quote_totals(
    application, organisation_id, account
):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id,
        quote.id,
        description="Design work",
        quantity=Decimal("10"),
        unit_price=Decimal("50.00"),
        tax_rate=Decimal("0.20"),
    )
    item = quote.line_items[0]
    assert item.net_total == Decimal("500.00")
    assert item.tax_amount == Decimal("100.00")
    assert item.total == Decimal("600.00")
    assert quote.subtotal == Decimal("500.00")
    assert quote.tax_total == Decimal("100.00")
    assert quote.total == Decimal("600.00")


def test_lines_can_carry_different_tax_rates_on_the_same_quote(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id,
        quote.id,
        description="Standard-rated",
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        tax_rate=Decimal("0.20"),
    )
    quote = application.quotes.add_line_item(
        organisation_id,
        quote.id,
        description="Zero-rated",
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        tax_rate=Decimal("0"),
    )
    assert quote.subtotal == Decimal("200")
    assert quote.tax_total == Decimal("20.00")
    assert quote.total == Decimal("220.00")


def test_tax_amount_is_rounded_to_the_nearest_cent(application, organisation_id, account):
    # 33.33 * 0.20 = 6.6660 exactly - a naive Decimal multiplication would
    # leave that extra digit rather than rounding to real money.
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id,
        quote.id,
        description="Design work",
        quantity=Decimal("1"),
        unit_price=Decimal("33.33"),
        tax_rate=Decimal("0.20"),
    )
    assert quote.line_items[0].tax_amount == Decimal("6.67")


@pytest.mark.parametrize("tax_rate", [Decimal("-0.01"), Decimal("1.01")])
def test_add_line_item_rejects_tax_rate_outside_zero_to_one(application, organisation_id, account, tax_rate):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    with pytest.raises(ValidationFailed):
        application.quotes.add_line_item(
            organisation_id,
            quote.id,
            description="x",
            quantity=Decimal("1"),
            unit_price=Decimal("1"),
            tax_rate=tax_rate,
        )


def test_converting_a_quote_to_an_invoice_carries_the_tax_rate_across(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id,
        quote.id,
        description="Design work",
        quantity=Decimal("10"),
        unit_price=Decimal("50.00"),
        tax_rate=Decimal("0.20"),
    )
    quote = application.quotes.send(organisation_id, quote.id)

    invoice = application.quotes.convert_to_invoice(organisation_id, quote.id)
    assert invoice.line_items[0].tax_rate == Decimal("0.20")
    assert invoice.total == Decimal("600.00")


def test_quote_numbers_increment_independently_of_invoice_numbers(application, organisation_id, account):
    first = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    first = application.quotes.add_line_item(
        organisation_id, first.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1")
    )
    first = application.quotes.send(organisation_id, first.id)
    second = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    second = application.quotes.add_line_item(
        organisation_id, second.id, description="y", quantity=Decimal("1"), unit_price=Decimal("1")
    )
    second = application.quotes.send(organisation_id, second.id)

    assert first.number == "Q-0001"
    assert second.number == "Q-0002"


def test_quote_numbers_are_independent_per_organisation(application, organisation_id, account):
    first = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    first = application.quotes.add_line_item(
        organisation_id, first.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1")
    )
    first = application.quotes.send(organisation_id, first.id)

    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    other_account = application.accounts.create_account(
        organisation_id=other_organisation_id, business_name="Other Co", email="b@b.test", address_line1="y"
    )
    second = application.quotes.create_quote(
        organisation_id=other_organisation_id, account_id=other_account.id
    )
    second = application.quotes.add_line_item(
        other_organisation_id, second.id, description="y", quantity=Decimal("1"), unit_price=Decimal("1")
    )
    second = application.quotes.send(other_organisation_id, second.id)

    assert first.number == "Q-0001"
    assert second.number == "Q-0001"
