from click.testing import CliRunner

from invoice_system.cli.main import cli


def test_full_cli_flow(tmp_path):
    db_path = tmp_path / "test.db"
    runner = CliRunner()

    result = runner.invoke(cli, ["--db", str(db_path), "init-db"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        cli,
        ["--db", str(db_path), "account", "create", "--business-name", "Acme", "--email", "a@b.test", "--address", "1 Main St"],
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
        ["--db", str(db_path), "quote", "add-item", "1", "--description", "Work", "--quantity", "1", "--unit-price", "100.00"],
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
