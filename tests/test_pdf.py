from datetime import UTC, datetime
from decimal import Decimal

from invoice_system.models import (
    Account,
    BusinessProfile,
    Invoice,
    InvoiceStatus,
    LineItem,
    Quote,
    QuoteStatus,
)
from invoice_system.pdf import (
    account_address_lines,
    bank_details_lines,
    business_profile_lines,
    expense_footer_lines,
    expense_header_lines,
    invoice_footer_lines,
    invoice_header_lines,
    quote_footer_lines,
    quote_header_lines,
    render_invoice_pdf,
    render_quote_pdf,
)


def _profile(**overrides: object) -> BusinessProfile:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    defaults: dict = {
        "id": 1,
        "user_id": 1,
        "title": None,
        "first_name": "Ada",
        "last_name": "Lovelace",
        "business_name": "Acme",
        "address_line1": None,
        "address_line2": None,
        "town_or_city": None,
        "county": None,
        "postcode": None,
        "payment_terms_days": 30,
        "quote_validity_days": 30,
        "currency": "GBP",
        "utr": None,
        "vat_number": None,
        "bank_account_name": None,
        "bank_sort_code": None,
        "bank_account_number": None,
        "quote_document_header": None,
        "quote_document_footer": None,
        "invoice_document_header": None,
        "invoice_document_footer": None,
        "expense_document_header": None,
        "expense_document_footer": None,
        "quote_number_prefix": "Q-",
        "quote_number_digits": 4,
        "invoice_number_prefix": "INV-",
        "invoice_number_digits": 4,
        "expense_number_prefix": "EXP-",
        "expense_number_digits": 4,
        "accent_color": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return BusinessProfile(**defaults)


def _account(**overrides: object) -> Account:
    defaults: dict = {
        "id": 1,
        "organisation_id": 1,
        "business_name": "Client Co",
        "contact_name": None,
        "email": "a@b.test",
        "phone": None,
        "address_line1": "1 Main St",
        "address_line2": None,
        "town_or_city": None,
        "county": None,
        "postcode": None,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Account(**defaults)


def test_no_profile_shows_nothing():
    assert business_profile_lines(None) == []


def test_profile_with_no_business_name_shows_nothing():
    assert business_profile_lines(_profile(business_name="")) == []


def test_business_name_only_when_no_address_set():
    assert business_profile_lines(_profile(business_name="Acme")) == ["Acme"]


def test_business_name_and_full_address_in_the_standard_uk_order():
    lines = business_profile_lines(
        _profile(
            business_name="Acme",
            address_line1="1 Main St",
            address_line2="Suite 4",
            town_or_city="London",
            county="Greater London",
            postcode="SW1A 1AA",
        )
    )
    assert lines == ["Acme", "1 Main St", "Suite 4", "London", "Greater London", "SW1A 1AA"]


def test_only_the_address_lines_that_are_set_appear():
    lines = business_profile_lines(
        _profile(business_name="Acme", address_line1="1 Main St", postcode="SW1A 1AA")
    )
    assert lines == ["Acme", "1 Main St", "SW1A 1AA"]


def test_blank_address_lines_are_treated_the_same_as_unset():
    assert business_profile_lines(_profile(business_name="Acme", address_line1="   ")) == ["Acme"]


def test_personal_name_never_appears_in_the_from_lines():
    lines = business_profile_lines(_profile(first_name="Ada", last_name="Lovelace", business_name="Acme"))
    assert "Ada" not in lines
    assert "Lovelace" not in lines


def test_account_address_line1_only_when_nothing_else_set():
    assert account_address_lines(_account(address_line1="1 Main St")) == ["1 Main St"]


def test_account_address_full_address_in_the_standard_uk_order():
    lines = account_address_lines(
        _account(
            address_line1="1 Main St",
            address_line2="Suite 4",
            town_or_city="London",
            county="Greater London",
            postcode="SW1A 1AA",
        )
    )
    assert lines == ["1 Main St", "Suite 4", "London", "Greater London", "SW1A 1AA"]


def test_account_address_only_the_lines_that_are_set_appear():
    lines = account_address_lines(_account(address_line1="1 Main St", postcode="SW1A 1AA"))
    assert lines == ["1 Main St", "SW1A 1AA"]


def test_no_profile_has_no_header_or_footer():
    assert quote_header_lines(None) == []
    assert quote_footer_lines(None) == []


def test_unset_header_and_footer_are_empty():
    assert quote_header_lines(_profile(quote_document_header=None)) == []
    assert quote_footer_lines(_profile(quote_document_footer=None)) == []


def test_header_splits_into_one_line_per_non_blank_line():
    lines = quote_header_lines(
        _profile(quote_document_header="Acme Ltd\n\nRegistered in England, company no. 12345678")
    )
    assert lines == ["Acme Ltd", "Registered in England, company no. 12345678"]


def test_footer_splits_into_one_line_per_non_blank_line():
    lines = quote_footer_lines(_profile(quote_document_footer="Thank you!\nPayment due within terms."))
    assert lines == ["Thank you!", "Payment due within terms."]


def test_header_and_footer_lines_are_individually_stripped():
    lines = quote_header_lines(_profile(quote_document_header="  Acme Ltd  \n  Suite 4  "))
    assert lines == ["Acme Ltd", "Suite 4"]


def test_blank_only_header_produces_no_lines():
    assert quote_header_lines(_profile(quote_document_header="   \n   ")) == []


def test_each_document_type_reads_only_its_own_header_and_footer_field():
    # quote_header_lines/invoice_header_lines/expense_header_lines (and
    # their _footer_ equivalents) are three independent pairs, not one
    # shared field read three ways - this is the property that actually
    # matters once they can diverge, distinct from the line-splitting
    # behaviour already covered above for one representative pair.
    profile = _profile(
        quote_document_header="quote header",
        quote_document_footer="quote footer",
        invoice_document_header="invoice header",
        invoice_document_footer="invoice footer",
        expense_document_header="expense header",
        expense_document_footer="expense footer",
    )
    assert quote_header_lines(profile) == ["quote header"]
    assert quote_footer_lines(profile) == ["quote footer"]
    assert invoice_header_lines(profile) == ["invoice header"]
    assert invoice_footer_lines(profile) == ["invoice footer"]
    assert expense_header_lines(profile) == ["expense header"]
    assert expense_footer_lines(profile) == ["expense footer"]


def test_rendering_a_quote_pdf_with_a_business_profile_set_does_not_error():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = _account(created_at=now)
    quote = Quote(
        id=1,
        organisation_id=1,
        account_id=1,
        number="Q-0001",
        status=QuoteStatus.SENT,
        currency="USD",
        issue_date=now.date(),
        expiry_date=None,
        created_at=now,
    )
    profile = _profile(business_name="Acme", address_line1="1 Main St", postcode="SW1A 1AA")
    pdf_bytes = render_quote_pdf(account, quote, profile)
    assert pdf_bytes.startswith(b"%PDF")


def test_rendering_a_quote_pdf_with_a_header_and_footer_does_not_error():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = _account(created_at=now)
    quote = Quote(
        id=1,
        organisation_id=1,
        account_id=1,
        number="Q-0001",
        status=QuoteStatus.SENT,
        currency="USD",
        issue_date=now.date(),
        expiry_date=None,
        created_at=now,
    )
    profile = _profile(
        quote_document_header="Acme Ltd\nRegistered in England, company no. 12345678",
        quote_document_footer="Thank you for your business!\nPayment due within terms.",
    )
    pdf_bytes = render_quote_pdf(account, quote, profile)
    assert pdf_bytes.startswith(b"%PDF")


def test_rendering_with_an_accent_color_set_does_not_error():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = _account(created_at=now)
    quote = Quote(
        id=1,
        organisation_id=1,
        account_id=1,
        number="Q-0001",
        status=QuoteStatus.SENT,
        currency="USD",
        issue_date=now.date(),
        expiry_date=None,
        created_at=now,
    )
    profile = _profile(accent_color="#2563EB")
    pdf_bytes = render_quote_pdf(account, quote, profile)
    assert pdf_bytes.startswith(b"%PDF")


def test_rendering_falls_back_to_a_default_accent_color_when_unset():
    # No BusinessProfile at all, and a BusinessProfile with accent_color
    # unset - both are "no profile to read a colour from" as far as
    # pdf.py's _render is concerned, and both should still render a
    # finished-looking document rather than erroring or leaving a colour
    # placeholder unresolved.
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = _account(created_at=now)
    quote = Quote(
        id=1,
        organisation_id=1,
        account_id=1,
        number="Q-0001",
        status=QuoteStatus.SENT,
        currency="USD",
        issue_date=now.date(),
        expiry_date=None,
        created_at=now,
    )
    assert render_quote_pdf(account, quote, None).startswith(b"%PDF")
    assert render_quote_pdf(account, quote, _profile(accent_color=None)).startswith(b"%PDF")


def test_no_profile_has_no_bank_details():
    assert bank_details_lines(None) == []


def test_unset_bank_details_are_empty():
    assert bank_details_lines(_profile()) == []


def test_bank_details_shows_only_the_fields_that_are_set():
    lines = bank_details_lines(_profile(bank_account_name="Acme", bank_sort_code="12-34-56"))
    assert lines == ["Account name: Acme", "Sort code: 12-34-56"]


def test_bank_details_full_set():
    lines = bank_details_lines(
        _profile(bank_account_name="Acme", bank_sort_code="12-34-56", bank_account_number="12345678")
    )
    assert lines == ["Account name: Acme", "Sort code: 12-34-56", "Account number: 12345678"]


def test_blank_bank_detail_fields_are_treated_the_same_as_unset():
    assert bank_details_lines(_profile(bank_account_name="   ")) == []


def test_rendering_an_invoice_pdf_with_bank_details_does_not_error():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = _account(created_at=now)
    invoice = Invoice(
        id=1,
        organisation_id=1,
        account_id=1,
        quote_id=None,
        number="INV-0001",
        status=InvoiceStatus.SENT,
        currency="USD",
        issue_date=now.date(),
        due_date=None,
        created_at=now,
    )
    profile = _profile(bank_account_name="Acme", bank_sort_code="12-34-56", bank_account_number="12345678")
    pdf_bytes = render_invoice_pdf(account, invoice, profile)
    assert pdf_bytes.startswith(b"%PDF")


def test_rendering_a_quote_pdf_with_a_from_profile_and_bill_to_side_by_side_does_not_error():
    # Exercises the two-column From/Bill-to Table layout specifically (only
    # taken when a business profile with a name is set).
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = _account(created_at=now, contact_name="Jane Doe", postcode="SW1A 1AA")
    quote = Quote(
        id=1,
        organisation_id=1,
        account_id=1,
        number="Q-0001",
        status=QuoteStatus.SENT,
        currency="USD",
        issue_date=now.date(),
        expiry_date=None,
        created_at=now,
    )
    profile = _profile(business_name="Acme", address_line1="1 Main St", postcode="SW1A 1AA")
    pdf_bytes = render_quote_pdf(account, quote, profile)
    assert pdf_bytes.startswith(b"%PDF")


def test_rendering_a_quote_pdf_with_taxed_line_items_does_not_error():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = _account(created_at=now)
    quote = Quote(
        id=1,
        organisation_id=1,
        account_id=1,
        number="Q-0001",
        status=QuoteStatus.SENT,
        currency="USD",
        issue_date=now.date(),
        expiry_date=None,
        created_at=now,
        line_items=[
            LineItem(
                id=1,
                description="Design work",
                quantity=Decimal("10"),
                unit_price=Decimal("50.00"),
                tax_rate=Decimal("0.20"),
                position=0,
            )
        ],
    )
    pdf_bytes = render_quote_pdf(account, quote, None)
    assert pdf_bytes.startswith(b"%PDF")


def test_rendering_a_long_line_item_description_does_not_error():
    # A long description (e.g. "Domain Registration - example.co.uk") used
    # to overflow the "Description" column into "Qty" rather than wrapping
    # - found from a real generated PDF. The line items table cell is now a
    # Paragraph, which wraps instead of overflowing; this can't assert the
    # visual layout without a PDF-parsing library this codebase doesn't
    # have, but it does prove the long-description path still renders.
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = _account(created_at=now)
    quote = Quote(
        id=1,
        organisation_id=1,
        account_id=1,
        number="Q-0001",
        status=QuoteStatus.SENT,
        currency="USD",
        issue_date=now.date(),
        expiry_date=None,
        created_at=now,
        line_items=[
            LineItem(
                id=1,
                description="Domain Registration and Renewal - a-very-long-example-domain-name.co.uk",
                quantity=Decimal("1"),
                unit_price=Decimal("12.00"),
                tax_rate=Decimal("0.20"),
                position=0,
            )
        ],
    )
    pdf_bytes = render_quote_pdf(account, quote, None)
    assert pdf_bytes.startswith(b"%PDF")


def test_rendering_escapes_special_characters_in_free_text_without_error():
    # reportlab's Paragraph interprets a small subset of HTML-like markup
    # in its text - confirmed by hand that an unescaped, unclosed-looking
    # tag (e.g. a line item description mentioning "<br>", or any other
    # unmatched "<...>") crashes doc.build() outright with a ValueError
    # ("syntax error"/"Parse error"), not just renders oddly - plausible
    # real input, not a contrived edge case (someone pasting from an HTML
    # source, or just typing "<" as a size comparison). Plain "&" alone
    # doesn't happen to crash reportlab's parser, but it's the same
    # unescaped-markup class of bug, so every free-text field below
    # exercises both. Covers every field that flows through a Paragraph:
    # line item description, account business/contact name and address,
    # and the "From" business profile/document header/footer.
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = _account(
        created_at=now,
        business_name="Smith & Sons <Ltd>",
        contact_name="Rock & Roll",
        address_line1="1 Main St & Co",
    )
    profile = _profile(
        business_name="Acme & Co",
        quote_document_header="Terms & Conditions apply",
        quote_document_footer="<Thank you> & goodbye",
    )
    quote = Quote(
        id=1,
        organisation_id=1,
        account_id=1,
        number="Q-0001",
        status=QuoteStatus.SENT,
        currency="USD",
        issue_date=now.date(),
        expiry_date=None,
        created_at=now,
        line_items=[
            LineItem(
                id=1,
                description="Domain Registration <br> and Renewal",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                tax_rate=Decimal("0.20"),
                position=0,
            )
        ],
    )
    pdf_bytes = render_quote_pdf(account, quote, profile)
    assert pdf_bytes.startswith(b"%PDF")
