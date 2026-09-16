import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from invoice_system.ids import new_id
from invoice_system.models import (
    Account,
    BusinessProfile,
    Expense,
    LineItem,
    Organisation,
    Quote,
    QuoteStatus,
)
from invoice_system.storage.schema import MIGRATIONS
from invoice_system.storage.sqlite_repository import SqliteRepository


@pytest.fixture
def repo(tmp_path):
    repository = SqliteRepository(tmp_path / "test.db")
    repository.migrate()
    yield repository
    repository.close()


@pytest.fixture
def organisation_id(repo) -> str:
    created = repo.create_organisation(
        Organisation(id=new_id(), name="Acme Org", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    )
    repo.add_organisation_member(created.id, user_id="user-1")
    return created.id


def test_migrate_is_idempotent(repo):
    repo.migrate()  # applying twice must not raise or duplicate schema objects


def test_migration_4_rescopes_number_uniqueness_to_per_organisation_and_preserves_data(tmp_path):
    # Freeze a database at migration 3 (before number uniqueness was
    # rescoped from a global column-level UNIQUE to a composite
    # (organisation_id, number) index - see schema.py) with an existing
    # quote, then confirm migration 4 both preserves it and actually
    # fixes the bug: two organisations can now share the same number.
    #
    # Ids here are plain integers, not UUIDs - migration 4 doesn't touch id
    # types at all (that's migration 7), so this frozen snapshot is
    # genuinely still on the old INTEGER AUTOINCREMENT schema. Only
    # migration 4's own script is applied (not repository.migrate(), which
    # would also run every later migration including migration 7's full
    # reset - see that test below - and wipe this data before it could be
    # asserted).
    db_path = tmp_path / "frozen.db"
    conn = sqlite3.connect(str(db_path))
    for version, script in enumerate(MIGRATIONS[:3], start=1):
        conn.executescript(script)
        conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()

    now = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    conn.execute("INSERT INTO organisations (id, name, created_at) VALUES (1, 'Org A', ?)", (now,))
    conn.execute("INSERT INTO organisations (id, name, created_at) VALUES (2, 'Org B', ?)", (now,))
    conn.execute(
        "INSERT INTO accounts (id, organisation_id, business_name, email, address, created_at) "
        "VALUES (1, 1, 'Acme', 'a@b.test', '1 Main St', ?)",
        (now,),
    )
    conn.execute(
        "INSERT INTO accounts (id, organisation_id, business_name, email, address, created_at) "
        "VALUES (2, 2, 'Other Co', 'b@b.test', '2 High St', ?)",
        (now,),
    )
    conn.execute(
        "INSERT INTO quotes (id, organisation_id, account_id, number, status, currency, issue_date, "
        "created_at) VALUES (1, 1, 1, 'Q-0001', 'sent', 'GBP', ?, ?)",
        ("2026-01-01", now),
    )
    conn.commit()

    conn.executescript(MIGRATIONS[3])
    conn.execute("PRAGMA user_version = 4")
    conn.commit()
    conn.close()

    repository = SqliteRepository(db_path)

    fetched = repository.get_quote(1, 1)
    assert fetched is not None
    assert fetched.number == "Q-0001"

    duplicate = repository.create_quote(
        Quote(
            id=3,
            organisation_id=2,
            account_id=2,
            number="Q-0001",
            status=QuoteStatus.SENT,
            currency="GBP",
            issue_date=datetime(2026, 1, 1, tzinfo=UTC).date(),
            expiry_date=None,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    assert duplicate.id is not None
    repository.close()


def test_migration_5_splits_account_address_into_structured_fields_and_preserves_data(tmp_path):
    # Freeze a database at migration 4 (before accounts.address was split
    # into address_line1/address_line2/town_or_city/county/postcode - see
    # schema.py) with an existing account, then confirm migration 5 moves
    # the old free-text value into address_line1 wholesale (never
    # discarded, never guessed-at-split) and leaves the rest NULL. Only
    # migration 5's own script is applied - see the migration 4 test above
    # for why not repository.migrate().
    db_path = tmp_path / "frozen.db"
    conn = sqlite3.connect(str(db_path))
    for version, script in enumerate(MIGRATIONS[:4], start=1):
        conn.executescript(script)
        conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()

    now = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    conn.execute("INSERT INTO organisations (id, name, created_at) VALUES (1, 'Org A', ?)", (now,))
    conn.execute(
        "INSERT INTO accounts (id, organisation_id, business_name, email, address, created_at) "
        "VALUES (1, 1, 'Acme', 'a@b.test', '12 Kings Road, London, SW1A 1AA', ?)",
        (now,),
    )
    conn.commit()

    conn.executescript(MIGRATIONS[4])
    conn.execute("PRAGMA user_version = 5")
    conn.commit()
    conn.close()

    repository = SqliteRepository(db_path)

    fetched = repository.get_account(1, 1)
    assert fetched is not None
    assert fetched.address_line1 == "12 Kings Road, London, SW1A 1AA"
    assert fetched.address_line2 is None
    assert fetched.town_or_city is None
    assert fetched.county is None
    assert fetched.postcode is None
    repository.close()


def test_migration_7_resets_ids_to_uuids(tmp_path):
    # Freeze a database at migration 6 (the last INTEGER-id schema) with
    # existing data, then confirm migration 7 - an authorized, one-time
    # full reset rather than a data-preserving migration (see schema.py) -
    # actually drops it: every table is empty afterwards, and a freshly
    # created row gets a real (non-integer) UUID4 id, not a resumed
    # autoincrement sequence.
    db_path = tmp_path / "frozen.db"
    conn = sqlite3.connect(str(db_path))
    for version, script in enumerate(MIGRATIONS[:6], start=1):
        conn.executescript(script)
        conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()

    now = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    conn.execute("INSERT INTO organisations (id, name, created_at) VALUES (1, 'Org A', ?)", (now,))
    conn.commit()
    conn.close()

    repository = SqliteRepository(db_path)
    repository.migrate()  # applies migration 7 and every migration after it

    assert repository.get_organisation_id_for_user("anyone") is None
    created = repository.create_organisation(
        Organisation(id=new_id(), name="Fresh Org", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert created.id != "1"
    assert len(created.id) == 36  # UUID4's canonical string length
    repository.close()


def test_migration_8_adds_expenses_without_touching_existing_data(tmp_path):
    # Migration 8 (expenses/expense_line_items) is purely additive - new
    # tables, no rebuild of any existing one (see schema.py) - so an
    # organisation created under migration 7's schema should still work
    # unchanged afterwards.
    db_path = tmp_path / "frozen.db"
    conn = sqlite3.connect(str(db_path))
    for version, script in enumerate(MIGRATIONS[:7], start=1):
        conn.executescript(script)
        conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()

    org_id = new_id()
    now = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    conn.execute("INSERT INTO organisations (id, name, created_at) VALUES (?, 'Org A', ?)", (org_id, now))
    conn.commit()
    conn.close()

    repository = SqliteRepository(db_path)
    repository.migrate()  # applies migration 8

    account = repository.create_account(_account(org_id))
    expense = repository.create_expense(
        Expense(
            id=new_id(),
            organisation_id=org_id,
            account_id=account.id,
            number=repository.next_expense_number(org_id),
            currency="GBP",
            issue_date=date(2026, 1, 1),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    assert expense.number == "EXP-0001"
    repository.close()


def test_get_organisation_id_for_user_returns_none_when_unset(repo):
    assert repo.get_organisation_id_for_user("user-1") is None


def test_create_organisation_and_add_member_round_trip(repo):
    created = repo.create_organisation(
        Organisation(id=new_id(), name="Acme Org", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert created.id is not None

    returned = repo.add_organisation_member(created.id, user_id="user-1")
    assert returned == created.id
    assert repo.get_organisation_id_for_user("user-1") == created.id


def test_add_organisation_member_is_idempotent_for_a_racing_second_organisation(repo):
    # Regression test: OrganisationService.get_or_create_for_user composes
    # a "does this user have an organisation" check with a create - two
    # concurrent first-ever calls for the same brand-new user can both
    # pass that check and then both try to become *the* organisation for
    # this user. add_organisation_member must resolve that race by
    # returning the first (winning) organisation_id rather than raising
    # on organisation_members.user_id's UNIQUE constraint.
    first = repo.create_organisation(
        Organisation(id=new_id(), name="First Org", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    )
    second = repo.create_organisation(
        Organisation(id=new_id(), name="Second Org", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    )

    assert repo.add_organisation_member(first.id, user_id="user-1") == first.id
    # The "losing" call - same user, a different organisation - must not
    # raise, and must report the organisation that actually won.
    assert repo.add_organisation_member(second.id, user_id="user-1") == first.id
    assert repo.get_organisation_id_for_user("user-1") == first.id


def _account(organisation_id: str, **overrides: object) -> Account:
    defaults: dict = {
        "id": new_id(),
        "organisation_id": organisation_id,
        "business_name": "Acme",
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


def test_account_round_trip_preserves_fields_and_tz(repo, organisation_id):
    created = repo.create_account(_account(organisation_id))
    assert created.id is not None

    fetched = repo.get_account(organisation_id, created.id)
    assert fetched.business_name == "Acme"
    assert fetched.created_at.tzinfo is not None


def test_account_round_trip_preserves_the_full_address(repo, organisation_id):
    created = repo.create_account(
        _account(
            organisation_id,
            address_line1="1 Main St",
            address_line2="Suite 4",
            town_or_city="London",
            county="Greater London",
            postcode="SW1A 1AA",
        )
    )

    fetched = repo.get_account(organisation_id, created.id)
    assert fetched.address_line1 == "1 Main St"
    assert fetched.address_line2 == "Suite 4"
    assert fetched.town_or_city == "London"
    assert fetched.county == "Greater London"
    assert fetched.postcode == "SW1A 1AA"


def test_get_missing_account_returns_none(repo, organisation_id):
    assert repo.get_account(organisation_id, "does-not-exist") is None


def test_get_account_from_another_organisation_returns_none(repo, organisation_id):
    created = repo.create_account(_account(organisation_id))

    other = repo.create_organisation(
        Organisation(id=new_id(), name="Other Org", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert repo.get_account(other.id, created.id) is None


def test_update_account_round_trip(repo, organisation_id):
    created = repo.create_account(_account(organisation_id))

    created.business_name = "Acme Ltd"
    created.contact_name = "Jane Doe"
    created.phone = "555-1234"
    created.address_line1 = "2 High St"
    created.town_or_city = "Bristol"
    updated = repo.update_account(created)
    assert updated.business_name == "Acme Ltd"

    fetched = repo.get_account(organisation_id, created.id)
    assert fetched.business_name == "Acme Ltd"
    assert fetched.contact_name == "Jane Doe"
    assert fetched.phone == "555-1234"
    assert fetched.address_line1 == "2 High St"
    assert fetched.town_or_city == "Bristol"


def test_list_accounts_is_ordered_by_creation_not_by_id(repo, organisation_id):
    # Ids are random UUID4s (see ids.py) with no ordering relationship to
    # insertion order - list_accounts orders by SQLite's implicit rowid
    # instead (see sqlite_repository.py's comment on list_accounts).
    first = repo.create_account(_account(organisation_id, business_name="A"))
    second = repo.create_account(_account(organisation_id, business_name="B"))

    fetched = repo.list_accounts(organisation_id)
    assert [a.business_name for a in fetched] == ["A", "B"]
    assert [a.id for a in fetched] == [first.id, second.id]


def test_next_number_increments_and_is_scoped_by_name(repo, organisation_id):
    assert repo.next_quote_number(organisation_id) == "Q-0001"
    assert repo.next_quote_number(organisation_id) == "Q-0002"
    assert repo.next_invoice_number(organisation_id) == "INV-0001"


def test_next_number_is_scoped_per_organisation(repo, organisation_id):
    other = repo.create_organisation(
        Organisation(id=new_id(), name="Other Org", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    )

    assert repo.next_quote_number(organisation_id) == "Q-0001"
    assert repo.next_quote_number(other.id) == "Q-0001"
    assert repo.next_quote_number(organisation_id) == "Q-0002"


def test_get_business_profile_returns_none_when_unset(repo):
    assert repo.get_business_profile(user_id="user-1") is None


def test_upsert_business_profile_round_trip_and_update(repo):
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    first = BusinessProfile(
        id=new_id(),
        user_id="user-1",
        title="Dr",
        first_name="Ada",
        last_name="Lovelace",
        business_name="Acme",
        address_line1="1 Main St",
        address_line2="Suite 4",
        town_or_city="London",
        county="Greater London",
        postcode="SW1A 1AA",
        payment_terms_days=30,
        currency="USD",
        utr="1234567890",
        vat_number=None,
        bank_account_name="Acme Ltd",
        bank_sort_code="12-34-56",
        bank_account_number="12345678",
        document_header="Acme Ltd",
        document_footer="Thank you!",
        created_at=created_at,
        updated_at=created_at,
    )
    inserted = repo.upsert_business_profile(first)
    assert inserted.id is not None

    fetched = repo.get_business_profile(user_id="user-1")
    assert fetched.title == "Dr"
    assert fetched.first_name == "Ada"
    assert fetched.last_name == "Lovelace"
    assert fetched.business_name == "Acme"
    assert fetched.address_line1 == "1 Main St"
    assert fetched.address_line2 == "Suite 4"
    assert fetched.town_or_city == "London"
    assert fetched.county == "Greater London"
    assert fetched.postcode == "SW1A 1AA"
    assert fetched.currency == "USD"
    assert fetched.utr == "1234567890"
    assert fetched.vat_number is None
    assert fetched.bank_account_name == "Acme Ltd"
    assert fetched.bank_sort_code == "12-34-56"
    assert fetched.bank_account_number == "12345678"
    assert fetched.document_header == "Acme Ltd"
    assert fetched.document_footer == "Thank you!"

    updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    second = BusinessProfile(
        id=new_id(),
        user_id="user-1",
        title=None,
        first_name="Grace",
        last_name="Hopper",
        business_name="Acme Ltd",
        address_line1=None,
        address_line2=None,
        town_or_city=None,
        county=None,
        postcode=None,
        payment_terms_days=14,
        currency="EUR",
        utr=None,
        vat_number="GB123456789",
        bank_account_name=None,
        bank_sort_code=None,
        bank_account_number=None,
        document_header=None,
        document_footer=None,
        created_at=created_at,
        updated_at=updated_at,
    )
    updated = repo.upsert_business_profile(second)

    assert updated.id == inserted.id  # same row, not a second one
    assert updated.title is None
    assert updated.first_name == "Grace"
    assert updated.business_name == "Acme Ltd"
    assert updated.address_line1 is None
    assert updated.payment_terms_days == 14
    assert updated.currency == "EUR"
    assert updated.utr is None
    assert updated.vat_number == "GB123456789"
    assert updated.bank_account_name is None
    assert updated.document_header is None


def test_expense_round_trip_with_line_items(repo, organisation_id):
    account = repo.create_account(_account(organisation_id))
    created = repo.create_expense(
        Expense(
            id=new_id(),
            organisation_id=organisation_id,
            account_id=account.id,
            number=repo.next_expense_number(organisation_id),
            currency="GBP",
            issue_date=date(2026, 1, 1),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    assert created.number == "EXP-0001"
    assert created.line_items == []

    repo.add_expense_line_item(
        created.id,
        LineItem(
            id=new_id(),
            description="Domain renewal",
            quantity=Decimal("1"),
            unit_price=Decimal("12.00"),
            tax_rate=Decimal("0.20"),
            position=0,
        ),
    )

    fetched = repo.get_expense(organisation_id, created.id)
    assert fetched.number == "EXP-0001"
    assert fetched.account_id == account.id
    assert [item.description for item in fetched.line_items] == ["Domain renewal"]
    assert fetched.total == Decimal("14.40")


def test_get_missing_expense_returns_none(repo, organisation_id):
    assert repo.get_expense(organisation_id, "does-not-exist") is None


def test_get_expense_from_another_organisation_returns_none(repo, organisation_id):
    account = repo.create_account(_account(organisation_id))
    created = repo.create_expense(
        Expense(
            id=new_id(),
            organisation_id=organisation_id,
            account_id=account.id,
            number=repo.next_expense_number(organisation_id),
            currency="GBP",
            issue_date=date(2026, 1, 1),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )

    other = repo.create_organisation(
        Organisation(id=new_id(), name="Other Org", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert repo.get_expense(other.id, created.id) is None


def test_list_expenses_is_ordered_by_creation_not_by_id(repo, organisation_id):
    account = repo.create_account(_account(organisation_id))

    def _expense(number: str) -> Expense:
        return Expense(
            id=new_id(),
            organisation_id=organisation_id,
            account_id=account.id,
            number=number,
            currency="GBP",
            issue_date=date(2026, 1, 1),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    first = repo.create_expense(_expense("EXP-0001"))
    second = repo.create_expense(_expense("EXP-0002"))

    fetched = repo.list_expenses(organisation_id)
    assert [e.id for e in fetched] == [first.id, second.id]


def test_list_expenses_filters_by_account(repo, organisation_id):
    account = repo.create_account(_account(organisation_id))
    other_account = repo.create_account(_account(organisation_id, business_name="Other"))

    def _expense(account_id: str, number: str) -> Expense:
        return Expense(
            id=new_id(),
            organisation_id=organisation_id,
            account_id=account_id,
            number=number,
            currency="GBP",
            issue_date=date(2026, 1, 1),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    repo.create_expense(_expense(account.id, "EXP-0001"))
    repo.create_expense(_expense(other_account.id, "EXP-0002"))

    assert len(repo.list_expenses(organisation_id)) == 2
    assert len(repo.list_expenses(organisation_id, account_id=account.id)) == 1


def test_next_expense_number_increments_and_is_scoped_per_organisation(repo, organisation_id):
    other = repo.create_organisation(
        Organisation(id=new_id(), name="Other Org", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    )

    assert repo.next_expense_number(organisation_id) == "EXP-0001"
    assert repo.next_expense_number(organisation_id) == "EXP-0002"
    assert repo.next_expense_number(other.id) == "EXP-0001"
