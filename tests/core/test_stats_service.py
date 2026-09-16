def test_get_stats_counts_zero_accounts_when_none_exist(application, organisation_id):
    stats = application.stats.get_stats(organisation_id)
    assert stats.account_count == 0


def test_get_stats_counts_all_accounts(application, organisation_id):
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="A", email="a@b.test", address="x"
    )
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="B", email="b@b.test", address="y"
    )

    stats = application.stats.get_stats(organisation_id)
    assert stats.account_count == 2


def test_get_stats_only_counts_accounts_in_the_same_organisation(application, organisation_id):
    application.accounts.create_account(
        organisation_id=organisation_id, business_name="A", email="a@b.test", address="x"
    )
    other_organisation_id = application.organisations.get_or_create_for_user(2)
    application.accounts.create_account(
        organisation_id=other_organisation_id, business_name="B", email="b@b.test", address="y"
    )

    stats = application.stats.get_stats(organisation_id)
    assert stats.account_count == 1
