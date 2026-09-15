from datetime import UTC, datetime

from invoice_system.models import Account, BusinessProfile, Quote, QuoteStatus
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
        "business_address": None,
        "payment_terms_days": 30,
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
    assert business_profile_lines(_profile(business_name="Acme", business_address=None)) == ["Acme"]


def test_business_name_and_address_when_both_set():
    lines = business_profile_lines(_profile(business_name="Acme", business_address="1 Main St"))
    assert lines == ["Acme", "1 Main St"]


def test_blank_address_is_treated_the_same_as_unset():
    assert business_profile_lines(_profile(business_name="Acme", business_address="   ")) == ["Acme"]


def test_personal_name_never_appears_in_the_from_lines():
    lines = business_profile_lines(_profile(first_name="Ada", last_name="Lovelace", business_name="Acme"))
    assert "Ada" not in lines
    assert "Lovelace" not in lines


def test_rendering_a_quote_pdf_with_a_business_profile_set_does_not_error():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    account = Account(
        id=1,
        business_name="Client Co",
        contact_name=None,
        email="a@b.test",
        phone=None,
        address="1 Main St",
        created_at=now,
    )
    quote = Quote(
        id=1,
        account_id=1,
        number="Q-0001",
        status=QuoteStatus.SENT,
        currency="USD",
        issue_date=now.date(),
        expiry_date=None,
        created_at=now,
    )
    pdf_bytes = render_quote_pdf(account, quote, _profile(business_name="Acme", business_address="1 Main St"))
    assert pdf_bytes.startswith(b"%PDF")
