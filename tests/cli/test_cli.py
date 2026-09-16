from datetime import date, timedelta

from click.testing import CliRunner

from invoice_system.cli.main import cli


def test_full_cli_flow(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()

    result = runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "account",
            "create",
            "--business-name",
            "Acme",
            "--email",
            "a@b.test",
            "--address",
            "1 Main St",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Created account 1" in result.output

    result = runner.invoke(cli, ["--db", str(db_path), "account", "list"])
    assert result.exit_code == 0, result.output
    assert "Acme" in result.output

    result = runner.invoke(cli, ["--db", str(db_path), "quote", "create", "--account-id", "1"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "quote",
            "add-item",
            "1",
            "--description",
            "Work",
            "--quantity",
            "1",
            "--unit-price",
            "100.00",
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli, ["--db", str(db_path), "quote", "send", "1"])
    assert result.exit_code == 0, result.output
    assert "Q-0001" in result.output

    pdf_path = tmp_path / "quote.pdf"
    result = runner.invoke(cli, ["--db", str(db_path), "quote", "pdf", "1", "-o", str(pdf_path)])
    assert result.exit_code == 0, result.output
    assert pdf_path.exists()

    result = runner.invoke(cli, ["--db", str(db_path), "quote", "convert", "1"])
    assert result.exit_code == 0, result.output
    assert "invoice 1" in result.output

    result = runner.invoke(cli, ["--db", str(db_path), "invoice", "list"])
    assert result.exit_code == 0, result.output
    assert "draft" in result.output

    result = runner.invoke(cli, ["--db", str(db_path), "invoice", "send", "1"])
    assert result.exit_code == 0, result.output
    assert "INV-0001" in result.output

    invoice_pdf_path = tmp_path / "invoice.pdf"
    result = runner.invoke(cli, ["--db", str(db_path), "invoice", "pdf", "1", "-o", str(invoice_pdf_path)])
    assert result.exit_code == 0, result.output
    assert invoice_pdf_path.exists()


def test_missing_account_returns_nonzero_exit(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])

    result = runner.invoke(cli, ["--db", str(db_path), "quote", "create", "--account-id", "999"])
    assert result.exit_code != 0


def test_quote_add_item_with_tax_rate(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "account",
            "create",
            "--business-name",
            "Acme",
            "--email",
            "a@b.test",
            "--address",
            "1 Main St",
        ],
    )
    runner.invoke(cli, ["--db", str(db_path), "quote", "create", "--account-id", "1"])

    result = runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "quote",
            "add-item",
            "1",
            "--description",
            "Design work",
            "--quantity",
            "1",
            "--unit-price",
            "100.00",
            "--tax-rate",
            "0.20",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Added line item" in result.output


def test_init_db_seeds_demo_data_by_default(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--db", str(db_path), "init-db"],
        env={"INVOICE_SYSTEM_AUTH_DB": str(tmp_path / "auth.db")},
    )
    assert result.exit_code == 0, result.output
    assert "demo data" in result.output.lower()

    result = runner.invoke(cli, ["--db", str(db_path), "stats"])
    assert "Accounts: " in result.output
    assert "Accounts: 0" not in result.output


def test_init_db_no_demo_skips_seeding(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "Database ready"

    result = runner.invoke(cli, ["--db", str(db_path), "stats"])
    assert "Accounts: 0" in result.output


def test_init_db_demo_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    env = {"INVOICE_SYSTEM_AUTH_DB": str(tmp_path / "auth.db")}
    runner.invoke(cli, ["--db", str(db_path), "init-db"], env=env)
    result = runner.invoke(cli, ["--db", str(db_path), "init-db"], env=env)

    assert result.exit_code == 0, result.output
    assert "already present" in result.output.lower()


def test_stats(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "account",
            "create",
            "--business-name",
            "Acme",
            "--email",
            "a@b.test",
            "--address",
            "1 Main St",
        ],
    )

    result = runner.invoke(cli, ["--db", str(db_path), "stats"])
    assert result.exit_code == 0, result.output
    assert "Accounts: 1" in result.output


def test_account_update(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "account",
            "create",
            "--business-name",
            "Acme",
            "--email",
            "a@b.test",
            "--address",
            "1 Main St",
        ],
    )

    result = runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "account",
            "update",
            "1",
            "--business-name",
            "Acme Ltd",
            "--email",
            "b@b.test",
            "--address",
            "2 High St",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Updated account 1: Acme Ltd" in result.output

    result = runner.invoke(cli, ["--db", str(db_path), "account", "list"])
    assert "Acme Ltd" in result.output


def test_account_update_missing_account_returns_nonzero_exit(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])

    result = runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "account",
            "update",
            "999",
            "--business-name",
            "Acme",
            "--email",
            "a@b.test",
            "--address",
            "1 Main St",
        ],
    )
    assert result.exit_code != 0


def test_settings_show_defaults_then_set_and_show_again(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])

    result = runner.invoke(cli, ["--db", str(db_path), "settings", "show", "--user-id", "1"])
    assert result.exit_code == 0, result.output
    assert "Payment terms (days): 30" in result.output
    assert "Currency: GBP" in result.output
    assert "Business name: -" in result.output

    result = runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "settings",
            "set",
            "--user-id",
            "1",
            "--first-name",
            "Ada",
            "--last-name",
            "Lovelace",
            "--business-name",
            "Acme Consulting",
            "--payment-terms-days",
            "5",
            "--currency",
            "usd",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Saved business profile for user 1" in result.output

    result = runner.invoke(cli, ["--db", str(db_path), "settings", "show", "--user-id", "1"])
    assert result.exit_code == 0, result.output
    assert "Name: Ada Lovelace" in result.output
    assert "Business name: Acme Consulting" in result.output
    assert "Address line 1: -" in result.output
    assert "Payment terms (days): 5" in result.output
    assert "Currency: USD" in result.output


def test_settings_set_requires_first_name(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])

    result = runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "settings",
            "set",
            "--user-id",
            "1",
            "--first-name",
            "",
            "--last-name",
            "Lovelace",
            "--business-name",
            "Acme",
        ],
    )
    assert result.exit_code != 0


def test_invoice_send_with_user_id_uses_the_profiles_payment_terms(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "settings",
            "set",
            "--user-id",
            "1",
            "--first-name",
            "Ada",
            "--last-name",
            "Lovelace",
            "--business-name",
            "Acme Consulting",
            "--payment-terms-days",
            "5",
        ],
    )
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "account",
            "create",
            "--business-name",
            "Client Co",
            "--email",
            "a@b.test",
            "--address",
            "1 Main St",
        ],
    )
    runner.invoke(cli, ["--db", str(db_path), "quote", "create", "--account-id", "1"])
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "quote",
            "add-item",
            "1",
            "--description",
            "Work",
            "--quantity",
            "1",
            "--unit-price",
            "100.00",
        ],
    )
    runner.invoke(cli, ["--db", str(db_path), "quote", "send", "1"])
    runner.invoke(cli, ["--db", str(db_path), "quote", "convert", "1"])

    result = runner.invoke(cli, ["--db", str(db_path), "invoice", "send", "1", "--user-id", "1"])
    assert result.exit_code == 0, result.output
    expected_due = date.today() + timedelta(days=5)
    assert f"due {expected_due.isoformat()}" in result.output


def test_invoice_pay(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "account",
            "create",
            "--business-name",
            "Client Co",
            "--email",
            "a@b.test",
            "--address",
            "1 Main St",
        ],
    )
    runner.invoke(cli, ["--db", str(db_path), "quote", "create", "--account-id", "1"])
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "quote",
            "add-item",
            "1",
            "--description",
            "Work",
            "--quantity",
            "1",
            "--unit-price",
            "100.00",
        ],
    )
    runner.invoke(cli, ["--db", str(db_path), "quote", "send", "1"])
    runner.invoke(cli, ["--db", str(db_path), "quote", "convert", "1"])
    runner.invoke(cli, ["--db", str(db_path), "invoice", "send", "1"])

    result = runner.invoke(cli, ["--db", str(db_path), "invoice", "pay", "1"])
    assert result.exit_code == 0, result.output
    assert "Invoice 1 marked paid" in result.output

    result = runner.invoke(cli, ["--db", str(db_path), "invoice", "list"])
    assert "paid" in result.output


def test_invoice_pay_a_draft_invoice_returns_nonzero_exit(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "account",
            "create",
            "--business-name",
            "Client Co",
            "--email",
            "a@b.test",
            "--address",
            "1 Main St",
        ],
    )
    runner.invoke(cli, ["--db", str(db_path), "quote", "create", "--account-id", "1"])
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "quote",
            "add-item",
            "1",
            "--description",
            "Work",
            "--quantity",
            "1",
            "--unit-price",
            "100.00",
        ],
    )
    runner.invoke(cli, ["--db", str(db_path), "quote", "send", "1"])
    runner.invoke(cli, ["--db", str(db_path), "quote", "convert", "1"])

    result = runner.invoke(cli, ["--db", str(db_path), "invoice", "pay", "1"])
    assert result.exit_code != 0


def test_invoice_monthly_totals(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "settings",
            "set",
            "--user-id",
            "1",
            "--first-name",
            "Ada",
            "--last-name",
            "Lovelace",
            "--business-name",
            "Acme Consulting",
            "--currency",
            "GBP",
        ],
    )

    result = runner.invoke(cli, ["--db", str(db_path), "invoice", "monthly-totals", "--user-id", "1"])
    assert result.exit_code == 0, result.output
    assert result.output.count("\n") == 12
    assert "GBP" in result.output


def test_quote_and_invoice_pdf_accept_a_user_id(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db", "--no-demo"])
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "settings",
            "set",
            "--user-id",
            "1",
            "--first-name",
            "Ada",
            "--last-name",
            "Lovelace",
            "--business-name",
            "Acme Consulting",
            "--address-line1",
            "1 Market St",
            "--town-or-city",
            "London",
            "--postcode",
            "SW1A 1AA",
        ],
    )
    runner.invoke(
        cli,
        [
            "--db",
            str(db_path),
            "account",
            "create",
            "--business-name",
            "Client Co",
            "--email",
            "a@b.test",
            "--address",
            "1 Main St",
        ],
    )
    runner.invoke(cli, ["--db", str(db_path), "quote", "create", "--account-id", "1"])

    pdf_path = tmp_path / "quote.pdf"
    result = runner.invoke(
        cli, ["--db", str(db_path), "quote", "pdf", "1", "-o", str(pdf_path), "--user-id", "1"]
    )
    assert result.exit_code == 0, result.output
    assert pdf_path.exists()
