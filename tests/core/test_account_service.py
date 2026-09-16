import pytest

from invoice_system.errors import NotFound, ValidationFailed


def test_create_and_get_account(application, organisation_id):
    account = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        contact_name="Jane Doe",
        email="jane@acme.test",
        phone="555-1234",
        address="1 Main St",
    )
    assert account.id is not None

    fetched = application.accounts.get_account(organisation_id, account.id)
    assert fetched.business_name == "Acme Co"
    assert fetched.contact_name == "Jane Doe"


@pytest.mark.parametrize("field", ["business_name", "email", "address"])
def test_create_account_requires_non_blank_fields(application, organisation_id, field):
    kwargs = {
        "organisation_id": organisation_id,
        "business_name": "Acme Co",
        "email": "jane@acme.test",
        "address": "1 Main St",
    }
    kwargs[field] = "   "
    with pytest.raises(ValidationFailed):
        application.accounts.create_account(**kwargs)


def test_get_missing_account_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.accounts.get_account(organisation_id, 999)


def test_list_accounts_is_ordered_by_creation(application, organisation_id):
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="A", email="a@b.test", address="x"
    )
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="B", email="b@b.test", address="y"
    )

    assert [a.business_name for a in application.accounts.list_accounts(organisation_id)] == ["A", "B"]


def test_accounts_are_isolated_per_organisation(application, organisation_id):
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="A", email="a@b.test", address="x"
    )
    other_organisation_id = application.organisations.get_or_create_for_user(2)
    application.accounts.create_account(
        organisation_id=other_organisation_id, business_name="B", email="b@b.test", address="y"
    )

    assert [a.business_name for a in application.accounts.list_accounts(organisation_id)] == ["A"]
    assert [a.business_name for a in application.accounts.list_accounts(other_organisation_id)] == ["B"]


def test_update_account_persists_changes(application, organisation_id):
    created = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        contact_name="Jane Doe",
        email="jane@acme.test",
        address="1 Main St",
    )

    updated = application.accounts.update_account(
        organisation_id,
        created.id,
        business_name="Acme Ltd",
        contact_name="Priya Patel",
        email="priya@acme.test",
        phone="555-9876",
        address="2 High St",
    )
    assert updated.id == created.id
    assert updated.business_name == "Acme Ltd"
    assert updated.contact_name == "Priya Patel"
    assert updated.email == "priya@acme.test"
    assert updated.phone == "555-9876"
    assert updated.address == "2 High St"

    fetched = application.accounts.get_account(organisation_id, created.id)
    assert fetched.business_name == "Acme Ltd"
    assert fetched.address == "2 High St"


def test_update_missing_account_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.accounts.update_account(
            organisation_id, 999, business_name="A", email="a@b.test", address="x"
        )


def test_update_account_from_another_organisation_raises_not_found(application, organisation_id):
    created = application.accounts.create_account(
        organisation_id=organisation_id, business_name="Acme Co", email="jane@acme.test", address="1 Main St"
    )
    other_organisation_id = application.organisations.get_or_create_for_user(2)

    with pytest.raises(NotFound):
        application.accounts.update_account(
            other_organisation_id, created.id, business_name="A", email="a@b.test", address="x"
        )


@pytest.mark.parametrize("field", ["business_name", "email", "address"])
def test_update_account_requires_non_blank_fields(application, organisation_id, field):
    created = application.accounts.create_account(
        organisation_id=organisation_id, business_name="Acme Co", email="jane@acme.test", address="1 Main St"
    )
    kwargs = {"business_name": "Acme Co", "email": "jane@acme.test", "address": "1 Main St"}
    kwargs[field] = "   "
    with pytest.raises(ValidationFailed):
        application.accounts.update_account(organisation_id, created.id, **kwargs)
