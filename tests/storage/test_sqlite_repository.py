from datetime import UTC, datetime

import pytest

from invoice_system.models import Account, BusinessProfile
from invoice_system.storage.sqlite_repository import SqliteRepository


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "test.db")
    repository.migrate()
    yield repository
    repository.close()


def test_migrate_is_idempotent(repo):
    repo.migrate()  # applying twice must not raise or duplicate schema objects


def test_account_round_trip_preserves_fields_and_tz(repo):
    account = Account(
        id=None,
        business_name="Acme",
        contact_name=None,
        email="a@b.test",
        phone=None,
        address="1 Main St",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    created = repo.create_account(account)
    assert created.id is not None

    fetched = repo.get_account(created.id)
    assert fetched.business_name == "Acme"
    assert fetched.created_at.tzinfo is not None


def test_get_missing_account_returns_none(repo):
    assert repo.get_account(999) is None


def test_next_number_increments_and_is_scoped_by_name(repo):
    assert repo.next_quote_number() == "Q-0001"
    assert repo.next_quote_number() == "Q-0002"
    assert repo.next_invoice_number() == "INV-0001"


def test_get_business_profile_returns_none_when_unset(repo):
    assert repo.get_business_profile(user_id=1) is None


def test_upsert_business_profile_round_trip_and_update(repo):
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    first = BusinessProfile(
        id=None,
        user_id=1,
        business_name="Acme",
        business_address="1 Main St",
        payment_terms_days=30,
        utr="1234567890",
        vat_number=None,
        created_at=created_at,
        updated_at=created_at,
    )
    inserted = repo.upsert_business_profile(first)
    assert inserted.id is not None

    fetched = repo.get_business_profile(user_id=1)
    assert fetched.business_name == "Acme"
    assert fetched.utr == "1234567890"
    assert fetched.vat_number is None

    updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    second = BusinessProfile(
        id=None,
        user_id=1,
        business_name="Acme Ltd",
        business_address="2 Main St",
        payment_terms_days=14,
        utr=None,
        vat_number="GB123456789",
        created_at=created_at,
        updated_at=updated_at,
    )
    updated = repo.upsert_business_profile(second)

    assert updated.id == inserted.id  # same row, not a second one
    assert updated.business_name == "Acme Ltd"
    assert updated.payment_terms_days == 14
    assert updated.utr is None
    assert updated.vat_number == "GB123456789"
