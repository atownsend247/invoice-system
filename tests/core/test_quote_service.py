from datetime import date
from decimal import Decimal

import pytest

from invoice_system.errors import InvalidTransition, NotFound, ValidationFailed
from invoice_system.models import ActivityEventType, QuoteStatus


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


def test_list_quotes_filters_by_account_name_and_status_and_paginates(application, organisation_id, account):
    northwind = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Northwind Traders",
        email="a@northwind.test",
        address_line1="2 Kings Road",
    )
    draft = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    sent = application.quotes.create_quote(organisation_id=organisation_id, account_id=northwind.id)
    sent = application.quotes.add_line_item(
        organisation_id, sent.id, description="Work", quantity=Decimal("1"), unit_price=Decimal("100.00")
    )
    sent = application.quotes.send(organisation_id, sent.id)

    by_account_name = application.quotes.list_quotes(organisation_id, account_name="northwind").items
    assert [q.id for q in by_account_name] == [sent.id]

    by_status = application.quotes.list_quotes(organisation_id, status=QuoteStatus.DRAFT).items
    assert [q.id for q in by_status] == [draft.id]

    page = application.quotes.list_quotes(organisation_id, page=1, page_size=1)
    assert len(page.items) == 1
    assert page.total == 2


@pytest.mark.parametrize(("page", "page_size"), [(0, 20), (1, 0), (1, 201)])
def test_list_quotes_rejects_invalid_pagination(application, organisation_id, page, page_size):
    with pytest.raises(ValidationFailed):
        application.quotes.list_quotes(organisation_id, page=page, page_size=page_size)


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


def test_create_quote_defaults_issue_date_to_today_and_computes_expiry(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    assert quote.issue_date == date(2026, 1, 1)  # fake_clock's fixed "now"
    assert quote.expiry_date == date(2026, 1, 31)  # + DEFAULT_QUOTE_VALIDITY_DAYS (30)


def test_create_quote_accepts_an_explicit_issue_date_and_validity(application, organisation_id, account):
    quote = application.quotes.create_quote(
        organisation_id=organisation_id,
        account_id=account.id,
        issue_date=date(2025, 12, 1),
        quote_validity_days=14,
    )
    assert quote.issue_date == date(2025, 12, 1)
    assert quote.expiry_date == date(2025, 12, 15)


def test_create_quote_records_a_created_event(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    assert len(quote.events) == 1
    event = quote.events[0]
    assert event.event_type == ActivityEventType.CREATED
    assert event.from_status is None
    assert event.to_status == QuoteStatus.DRAFT.value


def test_status_changes_are_recorded_newest_first(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id, quote.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1")
    )
    quote = application.quotes.send(organisation_id, quote.id)
    quote = application.quotes.mark_accepted(organisation_id, quote.id)

    assert [e.event_type for e in quote.events] == [
        ActivityEventType.STATUS_CHANGED,
        ActivityEventType.STATUS_CHANGED,
        ActivityEventType.CREATED,
    ]
    assert quote.events[0].from_status == QuoteStatus.SENT.value
    assert quote.events[0].to_status == QuoteStatus.ACCEPTED.value
    assert quote.events[1].from_status == QuoteStatus.DRAFT.value
    assert quote.events[1].to_status == QuoteStatus.SENT.value


def test_convert_to_invoice_defaults_issue_date_to_today(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id, quote.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1")
    )
    quote = application.quotes.send(organisation_id, quote.id)
    invoice = application.quotes.convert_to_invoice(organisation_id, quote.id)
    assert invoice.issue_date == date(2026, 1, 1)


def test_convert_to_invoice_accepts_a_backdated_issue_date(application, organisation_id, account):
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id, quote.id, description="x", quantity=Decimal("1"), unit_price=Decimal("1")
    )
    quote = application.quotes.send(organisation_id, quote.id)
    invoice = application.quotes.convert_to_invoice(organisation_id, quote.id, issue_date=date(2025, 11, 1))
    assert invoice.issue_date == date(2025, 11, 1)
    assert len(invoice.events) == 1
    assert invoice.events[0].event_type == ActivityEventType.CREATED


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
