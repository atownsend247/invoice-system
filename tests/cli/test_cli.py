from datetime import date, timedelta

from click.testing import CliRunner

from invoice_system.cli.main import cli


def test_full_cli_flow(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()

    result = runner.invoke(cli, ["--db", str(db_path), "init-db"])
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
    runner.invoke(cli, ["--db", str(db_path), "init-db"])

    result = runner.invoke(cli, ["--db", str(db_path), "quote", "create", "--account-id", "999"])
    assert result.exit_code != 0


def test_settings_show_defaults_then_set_and_show_again(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db"])

    result = runner.invoke(cli, ["--db", str(db_path), "settings", "show", "--user-id", "1"])
    assert result.exit_code == 0, result.output
    assert "Payment terms (days): 30" in result.output
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


def test_settings_set_requires_first_name(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db"])

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
    runner.invoke(cli, ["--db", str(db_path), "init-db"])
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


def test_quote_and_invoice_pdf_accept_a_user_id(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()
    runner.invoke(cli, ["--db", str(db_path), "init-db"])
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
