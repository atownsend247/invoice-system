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


def test_create_and_get_domain_linked_to_an_account(application, organisation_id, account):
    usage = application.domains.create_domain(
        organisation_id,
        domain_name="acme.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
        auto_renew=True,
        account_id=account.id,
    )
    assert usage.domain.id is not None
    assert usage.domain.account_id == account.id
    assert usage.domain.domain_name == "acme.test"
    assert usage.domain.expiry_date == date(2027, 1, 1)
    assert usage.domain.registrar == "123-Reg"
    assert usage.domain.auto_renew is True
    assert usage.account_name == "Acme Co"

    fetched = application.domains.get_domain(organisation_id, usage.domain.id)
    assert fetched.domain.domain_name == "acme.test"
    assert fetched.account_name == "Acme Co"


def test_create_domain_without_an_account_is_unlinked(application, organisation_id):
    usage = application.domains.create_domain(
        organisation_id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="123-Reg"
    )
    assert usage.domain.account_id is None
    assert usage.account_name is None


def test_create_domain_defaults_auto_renew_to_false(application, organisation_id):
    usage = application.domains.create_domain(
        organisation_id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="123-Reg"
    )
    assert usage.domain.auto_renew is False


def test_create_domain_requires_existing_account_when_given(application, organisation_id):
    with pytest.raises(NotFound):
        application.domains.create_domain(
            organisation_id,
            domain_name="acme.test",
            expiry_date=date(2027, 1, 1),
            registrar="123-Reg",
            account_id="does-not-exist",
        )


def test_create_domain_requires_account_in_same_organisation(application, organisation_id, account):
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.domains.create_domain(
            other_organisation_id,
            domain_name="acme.test",
            expiry_date=date(2027, 1, 1),
            registrar="123-Reg",
            account_id=account.id,
        )


@pytest.mark.parametrize("field", ["domain_name", "registrar"])
def test_create_domain_requires_non_blank_fields(application, organisation_id, field):
    kwargs = {"domain_name": "acme.test", "expiry_date": date(2027, 1, 1), "registrar": "123-Reg"}
    kwargs[field] = "   "
    with pytest.raises(ValidationFailed):
        application.domains.create_domain(organisation_id, **kwargs)


def test_list_domains_orders_soonest_expiry_first(application, organisation_id):
    application.domains.create_domain(
        organisation_id, domain_name="later.test", expiry_date=date(2027, 6, 1), registrar="R"
    )
    application.domains.create_domain(
        organisation_id, domain_name="sooner.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    domains = application.domains.list_domains(organisation_id)
    assert [d.domain.domain_name for d in domains] == ["sooner.test", "later.test"]


def test_list_domains_filters_by_account(application, organisation_id, account):
    other_account = application.accounts.create_account(
        organisation_id=organisation_id, business_name="B", email="b@b.test", address_line1="y"
    )
    application.domains.create_domain(
        organisation_id,
        domain_name="a.test",
        expiry_date=date(2027, 1, 1),
        registrar="R",
        account_id=account.id,
    )
    application.domains.create_domain(
        organisation_id,
        domain_name="b.test",
        expiry_date=date(2027, 1, 1),
        registrar="R",
        account_id=other_account.id,
    )
    application.domains.create_domain(
        organisation_id, domain_name="c.test", expiry_date=date(2027, 1, 1), registrar="R"
    )

    domains = application.domains.list_domains(organisation_id, account_id=account.id)
    assert [d.domain.domain_name for d in domains] == ["a.test"]


def test_list_domains_includes_unlinked_domains_by_default(application, organisation_id):
    application.domains.create_domain(
        organisation_id, domain_name="a.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    domains = application.domains.list_domains(organisation_id)
    assert [d.domain.domain_name for d in domains] == ["a.test"]
    assert domains[0].account_name is None


def test_get_missing_domain_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.domains.get_domain(organisation_id, "does-not-exist")


def test_domain_from_another_organisation_raises_not_found(application, organisation_id):
    usage = application.domains.create_domain(
        organisation_id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.domains.get_domain(other_organisation_id, usage.domain.id)


def test_update_domain_replaces_its_own_fields_but_not_the_account_link(
    application, organisation_id, account
):
    created = application.domains.create_domain(
        organisation_id,
        domain_name="acme.test",
        expiry_date=date(2027, 1, 1),
        registrar="123-Reg",
        auto_renew=False,
        account_id=account.id,
    )
    updated = application.domains.update_domain(
        organisation_id,
        created.domain.id,
        domain_name="acme.co.uk",
        expiry_date=date(2028, 1, 1),
        registrar="GoDaddy",
        auto_renew=True,
    )
    assert updated.domain.id == created.domain.id
    assert updated.domain.domain_name == "acme.co.uk"
    assert updated.domain.expiry_date == date(2028, 1, 1)
    assert updated.domain.registrar == "GoDaddy"
    assert updated.domain.auto_renew is True
    # update_domain never touches the link - still the same account.
    assert updated.domain.account_id == account.id
    assert updated.account_name == "Acme Co"


@pytest.mark.parametrize("field", ["domain_name", "registrar"])
def test_update_domain_requires_non_blank_fields(application, organisation_id, field):
    created = application.domains.create_domain(
        organisation_id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    kwargs = {
        "domain_name": "acme.test",
        "expiry_date": date(2027, 1, 1),
        "registrar": "R",
        "auto_renew": False,
    }
    kwargs[field] = "   "
    with pytest.raises(ValidationFailed):
        application.domains.update_domain(organisation_id, created.domain.id, **kwargs)


def test_update_missing_domain_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.domains.update_domain(
            organisation_id,
            "does-not-exist",
            domain_name="acme.test",
            expiry_date=date(2027, 1, 1),
            registrar="R",
            auto_renew=False,
        )


def test_link_domain_to_an_account(application, organisation_id, account):
    created = application.domains.create_domain(
        organisation_id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    assert created.domain.account_id is None

    linked = application.domains.link_domain(organisation_id, created.domain.id, account.id)
    assert linked.domain.account_id == account.id
    assert linked.account_name == "Acme Co"

    fetched = application.domains.get_domain(organisation_id, created.domain.id)
    assert fetched.domain.account_id == account.id


def test_link_domain_to_a_different_account_replaces_the_existing_link(application, organisation_id, account):
    other_account = application.accounts.create_account(
        organisation_id=organisation_id, business_name="Other Co", email="b@b.test", address_line1="y"
    )
    created = application.domains.create_domain(
        organisation_id,
        domain_name="acme.test",
        expiry_date=date(2027, 1, 1),
        registrar="R",
        account_id=account.id,
    )
    relinked = application.domains.link_domain(organisation_id, created.domain.id, other_account.id)
    assert relinked.domain.account_id == other_account.id
    assert relinked.account_name == "Other Co"


def test_link_domain_requires_existing_account(application, organisation_id):
    created = application.domains.create_domain(
        organisation_id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    with pytest.raises(NotFound):
        application.domains.link_domain(organisation_id, created.domain.id, "does-not-exist")


def test_link_missing_domain_raises_not_found(application, organisation_id, account):
    with pytest.raises(NotFound):
        application.domains.link_domain(organisation_id, "does-not-exist", account.id)


def test_unlink_domain(application, organisation_id, account):
    created = application.domains.create_domain(
        organisation_id,
        domain_name="acme.test",
        expiry_date=date(2027, 1, 1),
        registrar="R",
        account_id=account.id,
    )
    unlinked = application.domains.unlink_domain(organisation_id, created.domain.id)
    assert unlinked.domain.account_id is None
    assert unlinked.account_name is None

    fetched = application.domains.get_domain(organisation_id, created.domain.id)
    assert fetched.domain.account_id is None


def test_unlink_missing_domain_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.domains.unlink_domain(organisation_id, "does-not-exist")


def test_delete_domain(application, organisation_id):
    created = application.domains.create_domain(
        organisation_id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    application.domains.delete_domain(organisation_id, created.domain.id)
    with pytest.raises(NotFound):
        application.domains.get_domain(organisation_id, created.domain.id)


def test_delete_missing_domain_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.domains.delete_domain(organisation_id, "does-not-exist")


def test_domain_from_another_organisation_is_not_visible_in_list(application, organisation_id):
    application.domains.create_domain(
        organisation_id, domain_name="acme.test", expiry_date=date(2027, 1, 1), registrar="R"
    )
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    assert application.domains.list_domains(other_organisation_id) == []
