from decimal import Decimal


def test_get_stats_counts_zero_of_everything_when_nothing_exists(application, organisation_id):
    stats = application.stats.get_stats(organisation_id, "USD")
    assert stats.account_count == 0
    assert stats.quote_count == 0
    assert stats.invoice_count == 0
    assert stats.quotes_sent_count == 0
    assert stats.quotes_converted_count == 0
    assert stats.total_paid == Decimal("0")


def test_get_stats_counts_all_accounts(application, organisation_id):
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="A", email="a@b.test", address_line1="x"
    )
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="B", email="b@b.test", address_line1="y"
    )

    stats = application.stats.get_stats(organisation_id, "USD")
    assert stats.account_count == 2


def test_get_stats_only_counts_accounts_in_the_same_organisation(application, organisation_id):
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="A", email="a@b.test", address_line1="x"
    )
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    application.accounts.create_account(
        organisation_id=other_organisation_id, business_name="B", email="b@b.test", address_line1="y"
    )

    stats = application.stats.get_stats(organisation_id, "USD")
    assert stats.account_count == 1


def test_get_stats_counts_quotes_by_sent_and_converted_status(application, organisation_id):
    account = application.accounts.create_account(
        organisation_id=organisation_id, business_name="A", email="a@b.test", address_line1="x"
    )
    draft = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)

    sent = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    sent = application.quotes.add_line_item(
        organisation_id, sent.id, description="Work", quantity=Decimal("1"), unit_price=Decimal("10")
    )
    sent = application.quotes.send(organisation_id, sent.id)

    converted = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    converted = application.quotes.add_line_item(
        organisation_id, converted.id, description="Work", quantity=Decimal("1"), unit_price=Decimal("10")
    )
    converted = application.quotes.send(organisation_id, converted.id)
    application.quotes.convert_to_invoice(organisation_id, converted.id)

    stats = application.stats.get_stats(organisation_id, "USD")
    assert stats.quote_count == 3
    assert draft is not None  # kept as a draft, never sent
    assert stats.quotes_sent_count == 2  # sent + converted, not the draft
    assert stats.quotes_converted_count == 1


def test_get_stats_counts_all_invoices_regardless_of_status(application, organisation_id):
    account = application.accounts.create_account(
        organisation_id=organisation_id, business_name="A", email="a@b.test", address_line1="x"
    )
    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id, quote.id, description="Work", quantity=Decimal("1"), unit_price=Decimal("10")
    )
    quote = application.quotes.send(organisation_id, quote.id)
    application.quotes.convert_to_invoice(organisation_id, quote.id)

    stats = application.stats.get_stats(organisation_id, "USD")
    assert stats.invoice_count == 1


def test_get_stats_total_paid_only_counts_paid_invoices_in_the_given_currency(application, organisation_id):
    account = application.accounts.create_account(
        organisation_id=organisation_id, business_name="A", email="a@b.test", address_line1="x"
    )

    def _paid_invoice(*, currency: str, unit_price: Decimal) -> None:
        quote = application.quotes.create_quote(
            organisation_id=organisation_id, account_id=account.id, currency=currency
        )
        quote = application.quotes.add_line_item(
            organisation_id, quote.id, description="Work", quantity=Decimal("1"), unit_price=unit_price
        )
        quote = application.quotes.send(organisation_id, quote.id)
        invoice = application.quotes.convert_to_invoice(organisation_id, quote.id)
        invoice = application.invoices.send(organisation_id, invoice.id)
        application.invoices.pay(organisation_id, invoice.id)

    _paid_invoice(currency="USD", unit_price=Decimal("100.00"))
    _paid_invoice(currency="USD", unit_price=Decimal("50.00"))
    _paid_invoice(currency="GBP", unit_price=Decimal("999.00"))  # excluded - different currency

    quote = application.quotes.create_quote(organisation_id=organisation_id, account_id=account.id)
    quote = application.quotes.add_line_item(
        organisation_id, quote.id, description="Work", quantity=Decimal("1"), unit_price=Decimal("500.00")
    )
    quote = application.quotes.send(organisation_id, quote.id)
    unpaid = application.quotes.convert_to_invoice(organisation_id, quote.id)
    application.invoices.send(organisation_id, unpaid.id)  # sent but not paid - excluded

    stats = application.stats.get_stats(organisation_id, "USD")
    assert stats.total_paid == Decimal("150.00")
