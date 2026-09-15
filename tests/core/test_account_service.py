import pytest

from invoice_system.errors import NotFound, ValidationFailed


def test_create_and_get_account(application):
    account = application.accounts.create_account(
        business_name="Acme Co",
        contact_name="Jane Doe",
        email="jane@acme.test",
        phone="555-1234",
        address="1 Main St",
    )
    assert account.id is not None

    fetched = application.accounts.get_account(account.id)
    assert fetched.business_name == "Acme Co"
    assert fetched.contact_name == "Jane Doe"


@pytest.mark.parametrize("field", ["business_name", "email", "address"])
def test_create_account_requires_non_blank_fields(application, field):
    kwargs = {"business_name": "Acme Co", "email": "jane@acme.test", "address": "1 Main St"}
    kwargs[field] = "   "
    with pytest.raises(ValidationFailed):
        application.accounts.create_account(**kwargs)


def test_get_missing_account_raises_not_found(application):
    with pytest.raises(NotFound):
        application.accounts.get_account(999)


def test_list_accounts_is_ordered_by_creation(application):
    application.accounts.create_account(business_name="A", email="a@b.test", address="x")
    application.accounts.create_account(business_name="B", email="b@b.test", address="y")

    assert [a.business_name for a in application.accounts.list_accounts()] == ["A", "B"]
