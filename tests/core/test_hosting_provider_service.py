import pytest

from invoice_system.errors import Conflict, NotFound, ValidationFailed


def test_create_and_get_hosting_provider(application, organisation_id):
    hosting_provider = application.hosting_providers.create_hosting_provider(
        organisation_id, name="Acme Hosting", notes="https://acme-hosting.test"
    )
    assert hosting_provider.id is not None
    assert hosting_provider.organisation_id == organisation_id
    assert hosting_provider.name == "Acme Hosting"
    assert hosting_provider.notes == "https://acme-hosting.test"

    fetched = application.hosting_providers.get_hosting_provider(organisation_id, hosting_provider.id)
    assert fetched.name == "Acme Hosting"


def test_create_hosting_provider_notes_are_optional(application, organisation_id):
    hosting_provider = application.hosting_providers.create_hosting_provider(
        organisation_id, name="Acme Hosting"
    )
    assert hosting_provider.notes is None


def test_create_hosting_provider_blank_notes_are_stored_as_none(application, organisation_id):
    hosting_provider = application.hosting_providers.create_hosting_provider(
        organisation_id, name="Acme Hosting", notes="   "
    )
    assert hosting_provider.notes is None


def test_create_hosting_provider_requires_non_blank_name(application, organisation_id):
    with pytest.raises(ValidationFailed):
        application.hosting_providers.create_hosting_provider(organisation_id, name="   ")


def test_list_hosting_providers_orders_alphabetically(application, organisation_id):
    application.hosting_providers.create_hosting_provider(organisation_id, name="GoDaddy Hosting")
    application.hosting_providers.create_hosting_provider(organisation_id, name="Acme Hosting")
    application.hosting_providers.create_hosting_provider(organisation_id, name="namecheap")
    hosting_providers = application.hosting_providers.list_hosting_providers(organisation_id)
    assert [p.name for p in hosting_providers] == ["Acme Hosting", "GoDaddy Hosting", "namecheap"]


def test_hosting_providers_are_isolated_per_organisation(application, organisation_id):
    application.hosting_providers.create_hosting_provider(organisation_id, name="Acme Hosting")
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    assert application.hosting_providers.list_hosting_providers(other_organisation_id) == []


def test_get_missing_hosting_provider_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.hosting_providers.get_hosting_provider(organisation_id, "does-not-exist")


def test_hosting_provider_from_another_organisation_raises_not_found(application, organisation_id):
    hosting_provider = application.hosting_providers.create_hosting_provider(
        organisation_id, name="Acme Hosting"
    )
    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    with pytest.raises(NotFound):
        application.hosting_providers.get_hosting_provider(other_organisation_id, hosting_provider.id)


def test_update_hosting_provider_replaces_all_fields(application, organisation_id):
    hosting_provider = application.hosting_providers.create_hosting_provider(
        organisation_id, name="Acme Hosting"
    )
    updated = application.hosting_providers.update_hosting_provider(
        organisation_id, hosting_provider.id, name="Acme Hosting Ltd", notes="Transferred here"
    )
    assert updated.id == hosting_provider.id
    assert updated.name == "Acme Hosting Ltd"
    assert updated.notes == "Transferred here"

    fetched = application.hosting_providers.get_hosting_provider(organisation_id, hosting_provider.id)
    assert fetched.name == "Acme Hosting Ltd"


def test_update_hosting_provider_requires_non_blank_name(application, organisation_id):
    hosting_provider = application.hosting_providers.create_hosting_provider(
        organisation_id, name="Acme Hosting"
    )
    with pytest.raises(ValidationFailed):
        application.hosting_providers.update_hosting_provider(
            organisation_id, hosting_provider.id, name="   "
        )


def test_update_missing_hosting_provider_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.hosting_providers.update_hosting_provider(
            organisation_id, "does-not-exist", name="Acme Hosting"
        )


def test_delete_hosting_provider(application, organisation_id):
    hosting_provider = application.hosting_providers.create_hosting_provider(
        organisation_id, name="Acme Hosting"
    )
    application.hosting_providers.delete_hosting_provider(organisation_id, hosting_provider.id)
    with pytest.raises(NotFound):
        application.hosting_providers.get_hosting_provider(organisation_id, hosting_provider.id)


def test_delete_missing_hosting_provider_raises_not_found(application, organisation_id):
    with pytest.raises(NotFound):
        application.hosting_providers.delete_hosting_provider(organisation_id, "does-not-exist")


def test_list_hosting_providers_with_usage_reports_zero_for_an_unused_provider(application, organisation_id):
    application.hosting_providers.create_hosting_provider(organisation_id, name="Acme Hosting")
    [usage] = application.hosting_providers.list_hosting_providers_with_usage(organisation_id)
    assert usage.account_count == 0


def test_list_hosting_providers_with_usage_counts_distinct_accounts(application, organisation_id):
    application.hosting_providers.create_hosting_provider(organisation_id, name="Acme Hosting")
    application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="A",
        email="a@b.test",
        address_line1="1 Main St",
        hosting_provider="Acme Hosting",
    )
    application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="B",
        email="b@b.test",
        address_line1="2 High St",
        hosting_provider="Acme Hosting",
    )

    [usage] = application.hosting_providers.list_hosting_providers_with_usage(organisation_id)
    assert usage.account_count == 2


def test_list_hosting_providers_with_usage_is_isolated_per_organisation(application, organisation_id):
    application.hosting_providers.create_hosting_provider(organisation_id, name="Acme Hosting")
    application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="A",
        email="a@b.test",
        address_line1="1 Main St",
        hosting_provider="Acme Hosting",
    )

    other_organisation_id = application.organisations.get_or_create_for_user("user-2")
    application.hosting_providers.create_hosting_provider(other_organisation_id, name="Acme Hosting")
    [other_usage] = application.hosting_providers.list_hosting_providers_with_usage(other_organisation_id)
    assert other_usage.account_count == 0


def test_get_hosting_provider_usage_matches_by_current_name_not_a_stale_one(application, organisation_id):
    hosting_provider = application.hosting_providers.create_hosting_provider(
        organisation_id, name="Acme Hosting"
    )
    application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="A",
        email="a@b.test",
        address_line1="1 Main St",
        hosting_provider="Acme Hosting",
    )

    # An account recorded the old name as a plain string (see
    # models.Account) - renaming the hosting provider doesn't
    # retroactively update it, so usage under the *new* name is genuinely
    # zero even though one account still exists that used to match.
    application.hosting_providers.update_hosting_provider(
        organisation_id, hosting_provider.id, name="Big Hosting Co"
    )
    usage = application.hosting_providers.get_hosting_provider_usage(organisation_id, hosting_provider.id)
    assert usage.account_count == 0


def test_delete_hosting_provider_still_used_by_an_account_raises_conflict(application, organisation_id):
    hosting_provider = application.hosting_providers.create_hosting_provider(
        organisation_id, name="Acme Hosting"
    )
    application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="A",
        email="a@b.test",
        address_line1="1 Main St",
        hosting_provider="Acme Hosting",
    )
    with pytest.raises(Conflict):
        application.hosting_providers.delete_hosting_provider(organisation_id, hosting_provider.id)

    # Not actually deleted - the guard ran before the delete.
    assert (
        application.hosting_providers.get_hosting_provider(organisation_id, hosting_provider.id) is not None
    )


def test_delete_hosting_provider_succeeds_once_its_accounts_are_reassigned(application, organisation_id):
    hosting_provider = application.hosting_providers.create_hosting_provider(
        organisation_id, name="Acme Hosting"
    )
    account = application.accounts.create_account(
        organisation_id=organisation_id,
        business_name="A",
        email="a@b.test",
        address_line1="1 Main St",
        hosting_provider="Acme Hosting",
    )
    application.accounts.update_account(
        organisation_id,
        account.id,
        business_name="A",
        email="a@b.test",
        address_line1="1 Main St",
        hosting_provider=None,
    )

    application.hosting_providers.delete_hosting_provider(organisation_id, hosting_provider.id)
    with pytest.raises(NotFound):
        application.hosting_providers.get_hosting_provider(organisation_id, hosting_provider.id)
