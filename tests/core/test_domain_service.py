from datetime import date

import pytest

from invoice_system.errors import NotFound, ValidationFailed


@pytest.fixture
def account(application, organisation_id):
    return application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="Acme Co",
        email="jane@acme.test",
        address_line1="1 Main St",
    )


def test_create_and_get_domain(application, organisation_id, account):
    domain = application.domains.create_domain(
        organisation_id,
        account.id,
        domain_name="acme.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
        auto_renew=True,
    )
    assert domain.id is not None
    assert domain.account_id == account.id
    assert domain.domain_name == "acme.test"
    assert domain.expiry_date == date(2027, 1, 1)
    assert domain.registrar == "123-Reg"
    assert domain.auto_renew is True

    fetched = application.domains.get_domain(organisation_id, account.id, domain.id)
    assert fetched.domain_name == "acme.test"


def test_create_domain_defaults_auto_renew_to_false(application, organisation_id, account):
    domain = application.domains.create_domain(
        organisation_id,
        account.id,
        domain_name="acme.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
    )
    assert domain.auto_renew is False


def test_create_domain_requires_existing_account(application, organisation_id):
    with pytest.raises(NotFound):
        application.domains.create_domain(
            organisation_id,
            "does-not-exist",
            domain_name="acme.test",
            expiry_date=date(2027, 1, 1),
            registrar="123-Reg",
        )


def test_create_domain_requires_account_in_same_organisation(application, organisation_id, account):
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.domains.create_domain(
            other_organisation_id,
            account.id,
            domain_name="acme.test",
            expiry_date=date(2027, 1, 1),
            registrar="123-Reg",
        )


@pytest.mark.parametrize("field", ["domain_name", "registrar"])
def test_create_domain_requires_non_blank_fields(application, organisation_id, account, field):
    kwargs = {"domain_name": "acme.test", "expiry_date": date(2027, 1, 1), "registrar": "123-Reg"}
    kwargs[field] = "   "
    with pytest.raises(ValidationFailed):
        application.domains.create_domain(organisation_id, account.id, **kwargs)


def test_list_domains_orders_soonest_expiry_first(application, organisation_id, account):
    application.domains.create_domain(
        organisation_id, account.id, domain_name="later.test", expiry_date=date(2027, 6, 1), registrar="R"
    )
    application.domains.create_domain(
        organisation_id, account.id, domain_name="sooner.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    domains = application.domains.list_domains(organisation_id, account.id)
    assert [d.domain_name for d in domains] == ["sooner.test", "later.test"]


def test_list_domains_filters_by_account(application, organisation_id, account):
    other_account = application.accounts.create_account(
        organisation_id=organisation_id, business_name="B", email="b@b.test", address_line1="y"
    )
    application.domains.create_domain(
        organisation_id, account.id, domain_name="a.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    application.domains.create_domain(
        organisation_id, other_account.id, domain_name="b.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    domains = application.domains.list_domains(organisation_id, account.id)
    assert [d.domain_name for d in domains] == ["a.test"]


def test_get_missing_domain_raises_not_found(application, organisation_id, account):
    with pytest.raises(NotFound):
        application.domains.get_domain(organisation_id, account.id, "does-not-exist")


def test_domain_from_another_organisation_raises_not_found(application, organisation_id, account):
    domain = application.domains.create_domain(
        organisation_id, account.id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.domains.get_domain(other_organisation_id, account.id, domain.id)


def test_update_domain_replaces_all_fields(application, organisation_id, account):
    domain = application.domains.create_domain(
        organisation_id,
        account.id,
        domain_name="acme.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
        auto_renew=False,
    )
    updated = application.domains.update_domain(
        organisation_id,
        account.id,
        domain.id,
        domain_name="acme.co.uk",
        expiry_date=date(2028, 1, 1),
        registrar="GoDaddy",
        auto_renew=True,
    )
    assert updated.id == domain.id
    assert updated.domain_name == "acme.co.uk"
    assert updated.expiry_date == date(2028, 1, 1)
    assert updated.registrar == "GoDaddy"
    assert updated.auto_renew is True

    fetched = application.domains.get_domain(organisation_id, account.id, domain.id)
    assert fetched.domain_name == "acme.co.uk"


@pytest.mark.parametrize("field", ["domain_name", "registrar"])
def test_update_domain_requires_non_blank_fields(application, organisation_id, account, field):
    domain = application.domains.create_domain(
        organisation_id, account.id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    kwargs = {
        "domain_name": "acme.test",
        "expiry_date": date(2027, 1, 1),
        "registrar": "R",
        "auto_renew": False,
    }
    kwargs[field] = "   "
    with pytest.raises(ValidationFailed):
        application.domains.update_domain(organisation_id, account.id, domain.id, **kwargs)


def test_update_missing_domain_raises_not_found(application, organisation_id, account):
    with pytest.raises(NotFound):
        application.domains.update_domain(
            organisation_id,
            account.id,
            "does-not-exist",
            domain_name="acme.test",
            expiry_date=date(2027, 1, 1),
            registrar="R",
            auto_renew=False,
        )


def test_delete_domain(application, organisation_id, account):
    domain = application.domains.create_domain(
        organisation_id, account.id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    application.domains.delete_domain(organisation_id, account.id, domain.id)
    with pytest.raises(NotFound):
        application.domains.get_domain(organisation_id, account.id, domain.id)


def test_delete_missing_domain_raises_not_found(application, organisation_id, account):
    with pytest.raises(NotFound):
        application.domains.delete_domain(organisation_id, account.id, "does-not-exist")


def test_domain_from_another_account_is_not_visible(application, organisation_id, account):
    # Tenant/ownership isolation at the account level, not just the
    # organisation level - another account in the *same* organisation
    # still can't see/edit/delete this one's domain.
    other_account = application.accounts.create_account(
        organisation_id=organisation_id, business_name="B", email="b@b.test", address_line1="y"
    )
    domain = application.domains.create_domain(
        organisation_id, account.id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    with pytest.raises(NotFound):
        application.domains.get_domain(organisation_id, other_account.id, domain.id)
