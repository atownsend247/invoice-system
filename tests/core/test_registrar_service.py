from datetime import date

import pytest

from invoice_system.errors import Conflict, NotFound, ValidationFailed


@pytest.fixture
def account(application, organisation_id):
    return application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="jane@acme.test",
        address_line1="1 Main St",
    )


def test_create_and_get_registrar(application, organisation_id):
    registrar = application.registrars.create_registrar(
        organisation_id, name="123-Reg", notes="https://123-reg.co.uk"
    )
    assert registrar.id is not None
    assert registrar.organisation_id == organisation_id
    assert registrar.name == "123-Reg"
    assert registrar.notes == "https://123-reg.co.uk"

    fetched = application.registrars.get_registrar(organisation_id, registrar.id)
    assert fetched.name == "123-Reg"


def test_create_registrar_notes_are_optional(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    assert registrar.notes is None


def test_create_registrar_blank_notes_are_stored_as_none(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg", notes="   ")
    assert registrar.notes is None


def test_create_registrar_requires_non_blank_name(application, organisation_id):
    with pytest.raises(ValidationFailed):
        application.registrars.create_registrar(organisation_id, name="   ")


def test_list_registrars_orders_alphabetically(application, organisation_id):
    application.registrars.create_registrar(organisation_id, name="GoDaddy")
    application.registrars.create_registrar(organisation_id, name="123-Reg")
    application.registrars.create_registrar(organisation_id, name="namecheap")
    registrars = application.registrars.list_registrars(organisation_id)
    assert [r.name for r in registrars] == ["123-Reg", "GoDaddy", "namecheap"]


def test_registrars_are_isolated_per_organisation(application, organisation_id):
    application.registrars.create_registrar(organisation_id, name="123-Reg")
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    assert application.registrars.list_registrars(other_organisation_id) == []


def test_get_missing_registrar_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.registrars.get_registrar(organisation_id, "does-not-exist")


def test_registrar_from_another_organisation_raises_not_found(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.registrars.get_registrar(other_organisation_id, registrar.id)


def test_update_registrar_replaces_all_fields(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    updated = application.registrars.update_registrar(
        organisation_id, registrar.id, name="GoDaddy", notes="Transferred here"
    )
    assert updated.id == registrar.id
    assert updated.name == "GoDaddy"
    assert updated.notes == "Transferred here"

    fetched = application.registrars.get_registrar(organisation_id, registrar.id)
    assert fetched.name == "GoDaddy"


def test_update_registrar_requires_non_blank_name(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    with pytest.raises(ValidationFailed):
        application.registrars.update_registrar(organisation_id, registrar.id, name="   ")


def test_update_missing_registrar_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.registrars.update_registrar(organisation_id, "does-not-exist", name="GoDaddy")


def test_delete_registrar(application, organisation_id):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    application.registrars.delete_registrar(organisation_id, registrar.id)
    with pytest.raises(NotFound):
        application.registrars.get_registrar(organisation_id, registrar.id)


def test_delete_missing_registrar_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.registrars.delete_registrar(organisation_id, "does-not-exist")


def test_list_registrars_with_usage_reports_zero_for_an_unused_registrar(application, organisation_id):
    application.registrars.create_registrar(organisation_id, name="123-Reg")
    [usage] = application.registrars.list_registrars_with_usage(organisation_id)
    assert usage.domain_count == 0
    assert usage.account_count == 0


def test_list_registrars_with_usage_counts_domains_and_distinct_accounts(
    application, organisation_id, account
):
    application.registrars.create_registrar(organisation_id, name="123-Reg")
    other_account = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Other Co",
        email="pat@other.test",
        address_line1="2 High St",
    )
    application.domains.create_domain(
        organisation_id,
        domain_name="a.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
        account_id=account.id,
    )
    application.domains.create_domain(
        organisation_id,
        domain_name="b.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
        account_id=account.id,
    )
    application.domains.create_domain(
        organisation_id,
        domain_name="c.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
        account_id=other_account.id,
    )

    [usage] = application.registrars.list_registrars_with_usage(organisation_id)
    assert usage.domain_count == 3
    assert usage.account_count == 2


def test_list_registrars_with_usage_is_isolated_per_organisation(application, organisation_id, account):
    application.registrars.create_registrar(organisation_id, name="123-Reg")
    application.domains.create_domain(
        organisation_id,
        domain_name="a.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
        account_id=account.id,
    )

    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    application.registrars.create_registrar(other_organisation_id, name="123-Reg")
    [other_usage] = application.registrars.list_registrars_with_usage(other_organisation_id)
    assert other_usage.domain_count == 0


def test_get_registrar_usage_matches_by_current_name_not_a_stale_one(application, organisation_id, account):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    application.domains.create_domain(
        organisation_id,
        domain_name="a.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
        account_id=account.id,
    )

    # A domain recorded the old name as a plain string (see models.Domain) -
    # renaming the registrar doesn't retroactively update it, so usage
    # under the *new* name is genuinely zero even though one domain still
    # exists that used to match.
    application.registrars.update_registrar(organisation_id, registrar.id, name="GoDaddy")
    usage = application.registrars.get_registrar_usage(organisation_id, registrar.id)
    assert usage.domain_count == 0


def test_delete_registrar_still_used_by_a_domain_raises_conflict(application, organisation_id, account):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    application.domains.create_domain(
        organisation_id,
        domain_name="a.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
        account_id=account.id,
    )
    with pytest.raises(Conflict):
        application.registrars.delete_registrar(organisation_id, registrar.id)

    # Not actually deleted - the guard ran before the delete.
    assert application.registrars.get_registrar(organisation_id, registrar.id) is not None


def test_delete_registrar_succeeds_once_its_domains_are_gone(application, organisation_id, account):
    registrar = application.registrars.create_registrar(organisation_id, name="123-Reg")
    domain = application.domains.create_domain(
        organisation_id,
        domain_name="a.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
        account_id=account.id,
    )
    application.domains.delete_domain(organisation_id, domain.domain.id)

    application.registrars.delete_registrar(organisation_id, registrar.id)
    with pytest.raises(NotFound):
        application.registrars.get_registrar(organisation_id, registrar.id)
