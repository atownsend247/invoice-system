def test_get_stats_counts_zero_accounts_when_none_exist(application):
    stats = application.stats.get_stats()
    assert stats.account_count == 0


def test_get_stats_counts_all_accounts(application):
    application.accounts.create_account(business_name="A", email="a@b.test", address="x")
    application.accounts.create_account(business_name="B", email="b@b.test", address="y")

    stats = application.stats.get_stats()
    assert stats.account_count == 2
