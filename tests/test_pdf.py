from datetime import UTC, datetime
from decimal import Decimal

from invoice_system.models import Account, BusinessProfile, LineItem, Quote, QuoteStatus
from invoice_system.pdf import (
    account_address_lines,
    business_profile_lines,
    document_footer_lines,
    document_header_lines,
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
        "currency": "GBP",
        "utr": None,
        "vat_number": None,
        "bank_account_name": None,
        "bank_sort_code": None,
        "bank_account_number": None,
        "document_header": None,
        "document_footer": None,
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


def test_no_profile_has_no_document_header_or_footer():
    assert document_header_lines(None) == []
    assert document_footer_lines(None) == []


def test_unset_document_header_and_footer_are_empty():
    assert document_header_lines(_profile(document_header=None)) == []
    assert document_footer_lines(_profile(document_footer=None)) == []


def test_document_header_splits_into_one_line_per_non_blank_line():
    lines = document_header_lines(
        _profile(document_header="Acme Ltd\n\nRegistered in England, company no. 12345678")
    )
    assert lines == ["Acme Ltd", "Registered in England, company no. 12345678"]


def test_document_footer_splits_into_one_line_per_non_blank_line():
    lines = document_footer_lines(_profile(document_footer="Thank you!\nPayment due within terms."))
    assert lines == ["Thank you!", "Payment due within terms."]


def test_document_header_and_footer_lines_are_individually_stripped():
    lines = document_header_lines(_profile(document_header="  Acme Ltd  \n  Suite 4  "))
    assert lines == ["Acme Ltd", "Suite 4"]


def test_blank_only_document_header_produces_no_lines():
    assert document_header_lines(_profile(document_header="   \n   ")) == []


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


def test_rendering_a_quote_pdf_with_a_document_header_and_footer_does_not_error():
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
        document_header="Acme Ltd\nRegistered in England, company no. 12345678",
        document_footer="Thank you for your business!\nPayment due within terms.",
    )
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
