from datetime import UTC, datetime
from decimal import Decimal

from invoice_system.models import Account, BusinessProfile, LineItem, Quote, QuoteStatus
from invoice_system.pdf import business_profile_lines, render_quote_pdf


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
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return BusinessProfile(**defaults)


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


def test_rendering_a_quote_pdf_with_a_business_profile_set_does_not_error():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = Account(
        id=1,
        organisation_id=1,
        business_name="Client Co",
        contact_name=None,
        email="a@b.test",
        phone=None,
        address="1 Main St",
        created_at=now,
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
    )
    profile = _profile(business_name="Acme", address_line1="1 Main St", postcode="SW1A 1AA")
    pdf_bytes = render_quote_pdf(account, quote, profile)
    assert pdf_bytes.startswith(b"%PDF")


def test_rendering_a_quote_pdf_with_taxed_line_items_does_not_error():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = Account(
        id=1,
        organisation_id=1,
        business_name="Client Co",
        contact_name=None,
        email="a@b.test",
        phone=None,
        address="1 Main St",
        created_at=now,
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
