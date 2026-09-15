import sys
from decimal import Decimal
from pathlib import Path

import click

from ..errors import AppError
from ..factory import Application, build_application
from ..pdf import render_invoice_pdf, render_quote_pdf

DEFAULT_DB_PATH = "invoice_system.db"


@click.group()
@click.option(
    "--db", "db_path", default=DEFAULT_DB_PATH, show_default=True, help="Path to the SQLite database file."
)
@click.pass_context
def cli(ctx: click.Context, db_path: str) -> None:
    application = build_application(db_path)
    ctx.call_on_close(application.close)
    ctx.obj = application


@cli.command("init-db")
@click.pass_obj
def init_db(application: Application) -> None:
    click.echo("Database ready")


@cli.group()
def account() -> None:
    pass


@account.command("create")
@click.option("--business-name", required=True)
@click.option("--email", required=True)
@click.option("--address", required=True)
@click.option("--contact-name", default=None)
@click.option("--phone", default=None)
@click.pass_obj
def account_create(
    application: Application,
    business_name: str,
    email: str,
    address: str,
    contact_name: str | None,
    phone: str | None,
) -> None:
    created = application.accounts.create_account(
        business_name=business_name, email=email, address=address, contact_name=contact_name, phone=phone
    )
    click.echo(f"Created account {created.id}: {created.business_name}")


@account.command("list")
@click.pass_obj
def account_list(application: Application) -> None:
    for acc in application.accounts.list_accounts():
        click.echo(f"{acc.id}\t{acc.business_name}\t{acc.email}")


@cli.group()
def quote() -> None:
    pass


@quote.command("create")
@click.option("--account-id", type=int, required=True)
@click.option("--currency", default="USD", show_default=True)
@click.pass_obj
def quote_create(application: Application, account_id: int, currency: str) -> None:
    created = application.quotes.create_quote(account_id=account_id, currency=currency)
    click.echo(f"Created quote {created.id} (draft)")


@quote.command("add-item")
@click.argument("quote_id", type=int)
@click.option("--description", required=True)
@click.option("--quantity", required=True, type=Decimal)
@click.option("--unit-price", required=True, type=Decimal)
@click.pass_obj
def quote_add_item(
    application: Application, quote_id: int, description: str, quantity: Decimal, unit_price: Decimal
) -> None:
    application.quotes.add_line_item(
        quote_id, description=description, quantity=quantity, unit_price=unit_price
    )
    click.echo("Added line item")


@quote.command("send")
@click.argument("quote_id", type=int)
@click.pass_obj
def quote_send(application: Application, quote_id: int) -> None:
    sent = application.quotes.send(quote_id)
    click.echo(f"Quote {quote_id} sent as {sent.number}")


@quote.command("convert")
@click.argument("quote_id", type=int)
@click.pass_obj
def quote_convert(application: Application, quote_id: int) -> None:
    invoice = application.quotes.convert_to_invoice(quote_id)
    click.echo(f"Converted quote {quote_id} to invoice {invoice.id}")


@quote.command("pdf")
@click.argument("quote_id", type=int)
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option(
    "--user-id",
    type=int,
    default=None,
    help="Show this user's business profile as the 'From' party (see 'settings show'). "
    "Omit to render without one, same as before.",
)
@click.pass_obj
def quote_pdf(application: Application, quote_id: int, output: str, user_id: int | None) -> None:
    fetched = application.quotes.get_quote(quote_id)
    account = application.accounts.get_account(fetched.account_id)
    profile = application.business_profiles.get_profile(user_id) if user_id is not None else None
    Path(output).write_bytes(render_quote_pdf(account, fetched, profile))
    click.echo(f"Wrote {output}")


@cli.group()
def invoice() -> None:
    pass


@invoice.command("list")
@click.option("--account-id", type=int, default=None)
@click.pass_obj
def invoice_list(application: Application, account_id: int | None) -> None:
    for inv in application.invoices.list_invoices(account_id=account_id):
        click.echo(f"{inv.id}\t{inv.number or 'draft'}\t{inv.status.value}")


@invoice.command("send")
@click.argument("invoice_id", type=int)
@click.option(
    "--user-id",
    type=int,
    default=None,
    help="Use this user's payment terms (see 'settings show') for the due date. "
    "Omit to use the fixed default, same as before.",
)
@click.pass_obj
def invoice_send(application: Application, invoice_id: int, user_id: int | None) -> None:
    payment_terms_days = (
        application.business_profiles.get_profile(user_id).payment_terms_days if user_id is not None else None
    )
    sent = application.invoices.send(invoice_id, payment_terms_days=payment_terms_days)
    click.echo(f"Invoice {invoice_id} sent as {sent.number} (due {sent.due_date})")


@invoice.command("void")
@click.argument("invoice_id", type=int)
@click.pass_obj
def invoice_void(application: Application, invoice_id: int) -> None:
    application.invoices.void(invoice_id)
    click.echo(f"Invoice {invoice_id} voided")


@invoice.command("pay")
@click.argument("invoice_id", type=int)
@click.pass_obj
def invoice_pay(application: Application, invoice_id: int) -> None:
    application.invoices.pay(invoice_id)
    click.echo(f"Invoice {invoice_id} marked paid")


@invoice.command("monthly-totals")
@click.option(
    "--user-id",
    type=int,
    required=True,
    help="Resolve this user's reporting currency (see 'settings show') - only invoices in that "
    "currency are counted.",
)
@click.pass_obj
def invoice_monthly_totals(application: Application, user_id: int) -> None:
    profile = application.business_profiles.get_profile(user_id)
    for entry in application.invoices.monthly_totals(profile.currency):
        click.echo(
            f"{entry.month}\tpaid {entry.paid_total} {profile.currency}"
            f"\tunpaid {entry.unpaid_total} {profile.currency}"
        )


@invoice.command("pdf")
@click.argument("invoice_id", type=int)
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option(
    "--user-id",
    type=int,
    default=None,
    help="Show this user's business profile as the 'From' party (see 'settings show'). "
    "Omit to render without one, same as before.",
)
@click.pass_obj
def invoice_pdf(application: Application, invoice_id: int, output: str, user_id: int | None) -> None:
    fetched = application.invoices.get_invoice(invoice_id)
    account = application.accounts.get_account(fetched.account_id)
    profile = application.business_profiles.get_profile(user_id) if user_id is not None else None
    Path(output).write_bytes(render_invoice_pdf(account, fetched, profile))
    click.echo(f"Wrote {output}")


@cli.group()
def settings() -> None:
    pass


@settings.command("show")
@click.option("--user-id", type=int, required=True, help="sessionkit's User.id - see 'sessionkit list'.")
@click.pass_obj
def settings_show(application: Application, user_id: int) -> None:
    profile = application.business_profiles.get_profile(user_id)
    click.echo(f"Title: {profile.title or '-'}")
    click.echo(f"Name: {(profile.first_name + ' ' + profile.last_name).strip() or '-'}")
    click.echo(f"Business name: {profile.business_name or '-'}")
    click.echo(f"Address line 1: {profile.address_line1 or '-'}")
    click.echo(f"Address line 2: {profile.address_line2 or '-'}")
    click.echo(f"Town or city: {profile.town_or_city or '-'}")
    click.echo(f"County: {profile.county or '-'}")
    click.echo(f"Postcode: {profile.postcode or '-'}")
    click.echo(f"Payment terms (days): {profile.payment_terms_days}")
    click.echo(f"Currency: {profile.currency}")
    click.echo(f"UTR: {profile.utr or '-'}")
    click.echo(f"VAT number: {profile.vat_number or '-'}")


@settings.command("set")
@click.option("--user-id", type=int, required=True, help="sessionkit's User.id - see 'sessionkit list'.")
@click.option("--first-name", required=True)
@click.option("--last-name", required=True)
@click.option("--business-name", required=True)
@click.option("--title", default=None, help="Optional, e.g. Mr/Mrs/Dr.")
@click.option("--address-line1", default=None)
@click.option("--address-line2", default=None)
@click.option("--town-or-city", default=None)
@click.option("--county", default=None)
@click.option("--postcode", default=None)
@click.option("--payment-terms-days", type=int, default=30, show_default=True)
@click.option("--currency", default="GBP", show_default=True, help="Reporting currency, e.g. GBP/USD/EUR.")
@click.option("--utr", default=None)
@click.option("--vat-number", default=None)
@click.pass_obj
def settings_set(
    application: Application,
    user_id: int,
    first_name: str,
    last_name: str,
    business_name: str,
    title: str | None,
    address_line1: str | None,
    address_line2: str | None,
    town_or_city: str | None,
    county: str | None,
    postcode: str | None,
    payment_terms_days: int,
    currency: str,
    utr: str | None,
    vat_number: str | None,
) -> None:
    application.business_profiles.save_profile(
        user_id,
        title=title,
        first_name=first_name,
        last_name=last_name,
        business_name=business_name,
        address_line1=address_line1,
        address_line2=address_line2,
        town_or_city=town_or_city,
        county=county,
        postcode=postcode,
        payment_terms_days=payment_terms_days,
        currency=currency,
        utr=utr,
        vat_number=vat_number,
    )
    click.echo(f"Saved business profile for user {user_id}")


def main() -> None:
    try:
        cli(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except AppError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
