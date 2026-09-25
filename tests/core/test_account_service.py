import pytest

from invoice_system.errors import NotFound, ValidationFailed
from invoice_system.models import AccountStatus


def test_create_and_get_account(application, organisation_id):
    account = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        contact_name="Jane Doe",
        email="jane@acme.test",
        phone="555-1234",
        address_line1="1 Main St",
    )
    assert account.id is not None

    fetched = application.accounts.get_account(organisation_id, account.id)
    assert fetched.business_name == "Acme Co"
    assert fetched.contact_name == "Jane Doe"


def test_create_account_stores_the_full_address(application, organisation_id):
    account = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="jane@acme.test",
        address_line1="1 Main St",
        address_line2="Suite 4",
        town_or_city="London",
        county="Greater London",
        postcode="SW1A 1AA",
    )
    assert account.address_line1 == "1 Main St"
    assert account.address_line2 == "Suite 4"
    assert account.town_or_city == "London"
    assert account.county == "Greater London"
    assert account.postcode == "SW1A 1AA"


def test_create_account_normalises_blank_optional_address_lines_to_none(application, organisation_id):
    account = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="jane@acme.test",
        address_line1="1 Main St",
        address_line2="   ",
        town_or_city="",
    )
    assert account.address_line2 is None
    assert account.town_or_city is None


@pytest.mark.parametrize("field", ["business_name", "email", "address_line1"])
def test_create_account_requires_non_blank_fields(application, organisation_id, field):
    kwargs = {
        "organisation_id": organisation_id,
        "business_name": "Acme Co",
        "email": "jane@acme.test",
        "address_line1": "1 Main St",
    }
    kwargs[field] = "   "
    with pytest.raises(ValidationFailed):
        application.accounts.create_account(**kwargs)


def test_get_missing_account_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.accounts.get_account(organisation_id, 999)


def test_list_accounts_is_ordered_by_creation(application, organisation_id):
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="A", email="a@b.test", address_line1="x"
    )
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="B", email="b@b.test", address_line1="y"
    )

    assert [a.business_name for a in application.accounts.list_accounts(organisation_id).items] == ["A", "B"]


def test_list_accounts_paginates(application, organisation_id):
    for name in ["A", "B", "C"]:
        application.accounts.create_account(
            organisation_id=organisation_id, business_name=name, email="a@b.test", address_line1="x"
        )

    first_page = application.accounts.list_accounts(organisation_id, page=1, page_size=2)
    assert [a.business_name for a in first_page.items] == ["A", "B"]
    assert first_page.total == 3

    second_page = application.accounts.list_accounts(organisation_id, page=2, page_size=2)
    assert [a.business_name for a in second_page.items] == ["C"]
    assert second_page.total == 3


def test_list_accounts_query_matches_business_name_email_and_address(application, organisation_id):
    application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Northwind Traders",
        email="billing@northwind.test",
        address_line1="12 Kings Road",
    )
    application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Ltd",
        email="a@acme.test",
        address_line1="1 Main St",
    )

    matches = application.accounts.list_accounts(organisation_id, query="northwind").items
    assert [a.business_name for a in matches] == ["Northwind Traders"]

    matches = application.accounts.list_accounts(organisation_id, query="Kings Road").items
    assert [a.business_name for a in matches] == ["Northwind Traders"]

    assert application.accounts.list_accounts(organisation_id, query="nonexistent").items == []


@pytest.mark.parametrize(("page", "page_size"), [(0, 20), (-1, 20), (1, 0), (1, 201)])
def test_list_accounts_rejects_invalid_pagination(application, organisation_id, page, page_size):
    with pytest.raises(ValidationFailed):
        application.accounts.list_accounts(organisation_id, page=page, page_size=page_size)


def test_accounts_are_isolated_per_organisation(application, organisation_id):
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="A", email="a@b.test", address_line1="x"
    )
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    application.accounts.create_account(
        organisation_id=other_organisation_id, business_name="B", email="b@b.test", address_line1="y"
    )

    assert [a.business_name for a in application.accounts.list_accounts(organisation_id).items] == ["A"]
    assert [a.business_name for a in application.accounts.list_accounts(other_organisation_id).items] == ["B"]


def test_update_account_persists_changes(application, organisation_id):
    created = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        contact_name="Jane Doe",
        email="jane@acme.test",
        address_line1="1 Main St",
    )

    updated = application.accounts.update_account(
        organisation_id,
        created.id,
        business_name="Acme Ltd",
        contact_name="Priya Patel",
        email="priya@acme.test",
        phone="555-9876",
        address_line1="2 High St",
        town_or_city="Bristol",
        postcode="BS1 4ST",
        status=AccountStatus.ACTIVE,
    )
    assert updated.id == created.id
    assert updated.business_name == "Acme Ltd"
    assert updated.contact_name == "Priya Patel"
    assert updated.email == "priya@acme.test"
    assert updated.phone == "555-9876"
    assert updated.address_line1 == "2 High St"
    assert updated.town_or_city == "Bristol"
    assert updated.postcode == "BS1 4ST"

    fetched = application.accounts.get_account(organisation_id, created.id)
    assert fetched.business_name == "Acme Ltd"
    assert fetched.address_line1 == "2 High St"


def test_update_account_clears_optional_address_lines_left_blank(application, organisation_id):
    created = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="jane@acme.test",
        address_line1="1 Main St",
        town_or_city="London",
    )

    updated = application.accounts.update_account(
        organisation_id,
        created.id,
        business_name="Acme Co",
        email="jane@acme.test",
        address_line1="1 Main St",
        town_or_city="",
        status=AccountStatus.ACTIVE,
    )
    assert updated.town_or_city is None


def test_update_missing_account_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.accounts.update_account(
            organisation_id,
            999,
            business_name="A",
            email="a@b.test",
            address_line1="x",
            status=AccountStatus.ACTIVE,
        )


def test_update_account_from_another_organisation_raises_not_found(application, organisation_id):
    created = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="jane@acme.test",
        address_line1="1 Main St",
    )
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")

    with pytest.raises(NotFound):
        application.accounts.update_account(
            other_organisation_id,
            created.id,
            business_name="A",
            email="a@b.test",
            address_line1="x",
            status=AccountStatus.ACTIVE,
        )


@pytest.mark.parametrize("field", ["business_name", "email", "address_line1"])
def test_update_account_requires_non_blank_fields(application, organisation_id, field):
    created = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="jane@acme.test",
        address_line1="1 Main St",
    )
    kwargs = {
        "business_name": "Acme Co",
        "email": "jane@acme.test",
        "address_line1": "1 Main St",
        "status": AccountStatus.ACTIVE,
    }
    kwargs[field] = "   "
    with pytest.raises(ValidationFailed):
        application.accounts.update_account(organisation_id, created.id, **kwargs)


def test_create_account_defaults_status_to_new(application, organisation_id):
    account = application.accounts.create_account(
        organisation_id=organisation_id, business_name="Acme Co", email="a@b.test", address_line1="1 Main St"
    )
    assert account.status == AccountStatus.NEW


def test_create_account_accepts_an_explicit_status_and_hosting_provider(application, organisation_id):
    account = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="a@b.test",
        address_line1="1 Main St",
        status=AccountStatus.ACTIVE,
        hosting_provider="Acme Hosting",
    )
    assert account.status == AccountStatus.ACTIVE
    assert account.hosting_provider == "Acme Hosting"


def test_update_account_changes_status_and_hosting_provider(application, organisation_id):
    created = application.accounts.create_account(
        organisation_id=organisation_id, business_name="Acme Co", email="a@b.test", address_line1="1 Main St"
    )
    assert created.status == AccountStatus.NEW

    updated = application.accounts.update_account(
        organisation_id,
        created.id,
        business_name="Acme Co",
        email="a@b.test",
        address_line1="1 Main St",
        status=AccountStatus.CLOSED,
        hosting_provider="Acme Hosting",
    )
    assert updated.status == AccountStatus.CLOSED
    assert updated.hosting_provider == "Acme Hosting"

    fetched = application.accounts.get_account(organisation_id, created.id)
    assert fetched.status == AccountStatus.CLOSED
    assert fetched.hosting_provider == "Acme Hosting"


def test_update_account_clears_hosting_provider_left_blank(application, organisation_id):
    created = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="a@b.test",
        address_line1="1 Main St",
        hosting_provider="Acme Hosting",
    )

    updated = application.accounts.update_account(
        organisation_id,
        created.id,
        business_name="Acme Co",
        email="a@b.test",
        address_line1="1 Main St",
        status=AccountStatus.NEW,
        hosting_provider="   ",
    )
    assert updated.hosting_provider is None
