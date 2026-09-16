import os
import sys
from decimal import Decimal
from pathlib import Path

import click

from ..auth import DEFAULT_AUTH_DB_PATH, build_auth
from ..demo_data import DEMO_EMAIL, DEMO_PASSWORD, seed_demo_data
from ..errors import AppError
from ..factory import Application, build_application
from ..pdf import render_invoice_pdf, render_quote_pdf

DEFAULT_DB_PATH = "invoice_system.db"

_USER_ID_HELP = (
    "sessionkit's User.id (see 'sessionkit list') - resolves which organisation's data to use "
    "(auto-created on first use per user, see CLAUDE.md); required since the CLI has no login "
    "session to infer it from."
)


def _organisation_id(application: Application, user_id: int) -> int:
    return application.organisations.get_or_create_for_user(user_id)


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
@click.option(
    "--demo/--no-demo",
    default=True,
    show_default=True,
    help="Seed a demo login user, business profile, accounts, and a year of quotes/invoices "
    "in a mix of statuses. Safe to repeat - a no-op once the demo user already exists.",
)
@click.pass_obj
def init_db(application: Application, demo: bool) -> None:
    if not demo:
        click.echo("Database ready")
        return

    auth_db_path = os.environ.get("INVOICE_SYSTEM_AUTH_DB", DEFAULT_AUTH_DB_PATH)
    auth = build_auth(auth_db_path)
    try:
        seeded = seed_demo_data(application, auth)
    finally:
        auth.close()

    if seeded:
        click.echo(f"Database ready with demo data (log in as {DEMO_EMAIL} / {DEMO_PASSWORD})")
    else:
        click.echo("Database ready (demo data already present)")


@cli.group()
def account() -> None:
    pass


@account.command("create")
@click.option("--user-id", type=int, required=True, help=_USER_ID_HELP)
@click.option("--business-name", required=True)
@click.option("--email", required=True)
@click.option("--address-line1", required=True)
@click.option("--contact-name", default=None)
@click.option("--phone", default=None)
@click.option("--address-line2", default=None)
@click.option("--town-or-city", default=None)
@click.option("--county", default=None)
@click.option("--postcode", default=None)
@click.pass_obj
def account_create(
    application: Application,
    user_id: int,
    business_name: str,
    email: str,
    address_line1: str,
    contact_name: str | None,
    phone: str | None,
    address_line2: str | None,
    town_or_city: str | None,
    county: str | None,
    postcode: str | None,
) -> None:
    created = application.accounts.create_account(
        organisation_id=_organisation_id(application, user_id),
        business_name=business_name,
        email=email,
        address_line1=address_line1,
        contact_name=contact_name,
        phone=phone,
        address_line2=address_line2,
        town_or_city=town_or_city,
        county=county,
        postcode=postcode,
    )
    click.echo(f"Created account {created.id}: {created.business_name}")


@account.command("list")
@click.option("--user-id", type=int, required=True, help=_USER_ID_HELP)
@click.pass_obj
def account_list(application: Application, user_id: int) -> None:
    for acc in application.accounts.list_accounts(_organisation_id(application, user_id)):
        click.echo(f"{acc.id}\t{acc.business_name}\t{acc.email}")


@account.command("update")
@click.argument("account_id", type=int)
@click.option("--user-id", type=int, required=True, help=_USER_ID_HELP)
@click.option("--business-name", required=True)
@click.option("--email", required=True)
@click.option("--address-line1", required=True)
@click.option("--contact-name", default=None)
@click.option("--phone", default=None)
@click.option("--address-line2", default=None)
@click.option("--town-or-city", default=None)
@click.option("--county", default=None)
@click.option("--postcode", default=None)
@click.pass_obj
def account_update(
    application: Application,
    account_id: int,
    user_id: int,
    business_name: str,
    email: str,
    address_line1: str,
    contact_name: str | None,
    phone: str | None,
    address_line2: str | None,
    town_or_city: str | None,
    county: str | None,
    postcode: str | None,
) -> None:
    updated = application.accounts.update_account(
        _organisation_id(application, user_id),
        account_id,
        business_name=business_name,
        email=email,
        address_line1=address_line1,
        contact_name=contact_name,
        phone=phone,
        address_line2=address_line2,
        town_or_city=town_or_city,
        county=county,
        postcode=postcode,
    )
    click.echo(f"Updated account {updated.id}: {updated.business_name}")


@cli.group()
def quote() -> None:
    pass


@quote.command("create")
@click.option("--user-id", type=int, required=True, help=_USER_ID_HELP)
@click.option("--account-id", type=int, required=True)
@click.option("--currency", default="USD", show_default=True)
@click.pass_obj
def quote_create(application: Application, user_id: int, account_id: int, currency: str) -> None:
    created = application.quotes.create_quote(
        organisation_id=_organisation_id(application, user_id), account_id=account_id, currency=currency
    )
    click.echo(f"Created quote {created.id} (draft)")


@quote.command("add-item")
@click.argument("quote_id", type=int)
@click.option("--user-id", type=int, required=True, help=_USER_ID_HELP)
@click.option("--description", required=True)
@click.option("--quantity", required=True, type=Decimal)
@click.option("--unit-price", required=True, type=Decimal)
@click.option(
    "--tax-rate",
    default="0",
    type=Decimal,
    show_default=True,
    help="VAT/tax rate as a fraction, e.g. 0.20 for 20%.",
)
@click.pass_obj
def quote_add_item(
    application: Application,
    quote_id: int,
    user_id: int,
    description: str,
    quantity: Decimal,
    unit_price: Decimal,
    tax_rate: Decimal,
) -> None:
    application.quotes.add_line_item(
        _organisation_id(application, user_id),
        quote_id,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        tax_rate=tax_rate,
    )
    click.echo("Added line item")


@quote.command("send")
@click.argument("quote_id", type=int)
@click.option("--user-id", type=int, required=True, help=_USER_ID_HELP)
@click.pass_obj
def quote_send(application: Application, quote_id: int, user_id: int) -> None:
    sent = application.quotes.send(_organisation_id(application, user_id), quote_id)
    click.echo(f"Quote {quote_id} sent as {sent.number}")


@quote.command("convert")
@click.argument("quote_id", type=int)
@click.option("--user-id", type=int, required=True, help=_USER_ID_HELP)
@click.pass_obj
def quote_convert(application: Application, quote_id: int, user_id: int) -> None:
    invoice = application.quotes.convert_to_invoice(_organisation_id(application, user_id), quote_id)
    click.echo(f"Converted quote {quote_id} to invoice {invoice.id}")


@quote.command("pdf")
@click.argument("quote_id", type=int)
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option(
    "--user-id",
    type=int,
    required=True,
    help=_USER_ID_HELP + " Also shown on the PDF as the 'From' party (see 'settings show'), if set.",
)
@click.pass_obj
def quote_pdf(application: Application, quote_id: int, output: str, user_id: int) -> None:
    organisation_id = _organisation_id(application, user_id)
    fetched = application.quotes.get_quote(organisation_id, quote_id)
    account = application.accounts.get_account(organisation_id, fetched.account_id)
    profile = application.business_profiles.get_profile(user_id)
    Path(output).write_bytes(render_quote_pdf(account, fetched, profile))
    click.echo(f"Wrote {output}")


@cli.group()
def invoice() -> None:
    pass


@invoice.command("list")
@click.option("--user-id", type=int, required=True, help=_USER_ID_HELP)
@click.option("--account-id", type=int, default=None)
@click.pass_obj
def invoice_list(application: Application, user_id: int, account_id: int | None) -> None:
    organisation_id = _organisation_id(application, user_id)
    for inv in application.invoices.list_invoices(organisation_id, account_id=account_id):
        click.echo(f"{inv.id}\t{inv.number or 'draft'}\t{inv.status.value}")


@invoice.command("send")
@click.argument("invoice_id", type=int)
@click.option(
    "--user-id",
    type=int,
    required=True,
    help=_USER_ID_HELP + " Also uses this user's payment terms (see 'settings show') for the due date.",
)
@click.pass_obj
def invoice_send(application: Application, invoice_id: int, user_id: int) -> None:
    organisation_id = _organisation_id(application, user_id)
    payment_terms_days = application.business_profiles.get_profile(user_id).payment_terms_days
    sent = application.invoices.send(organisation_id, invoice_id, payment_terms_days=payment_terms_days)
    click.echo(f"Invoice {invoice_id} sent as {sent.number} (due {sent.due_date})")


@invoice.command("void")
@click.argument("invoice_id", type=int)
@click.option("--user-id", type=int, required=True, help=_USER_ID_HELP)
@click.pass_obj
def invoice_void(application: Application, invoice_id: int, user_id: int) -> None:
    application.invoices.void(_organisation_id(application, user_id), invoice_id)
    click.echo(f"Invoice {invoice_id} voided")


@invoice.command("pay")
@click.argument("invoice_id", type=int)
@click.option("--user-id", type=int, required=True, help=_USER_ID_HELP)
@click.pass_obj
def invoice_pay(application: Application, invoice_id: int, user_id: int) -> None:
    application.invoices.pay(_organisation_id(application, user_id), invoice_id)
    click.echo(f"Invoice {invoice_id} marked paid")


@invoice.command("monthly-totals")
@click.option(
    "--user-id",
    type=int,
    required=True,
    help=_USER_ID_HELP + " Also resolves this user's reporting currency (see 'settings show') - only "
    "invoices in that currency are counted.",
)
@click.pass_obj
def invoice_monthly_totals(application: Application, user_id: int) -> None:
    organisation_id = _organisation_id(application, user_id)
    profile = application.business_profiles.get_profile(user_id)
    for entry in application.invoices.monthly_totals(organisation_id, profile.currency):
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
    required=True,
    help=_USER_ID_HELP + " Also shown on the PDF as the 'From' party (see 'settings show'), if set.",
)
@click.pass_obj
def invoice_pdf(application: Application, invoice_id: int, output: str, user_id: int) -> None:
    organisation_id = _organisation_id(application, user_id)
    fetched = application.invoices.get_invoice(organisation_id, invoice_id)
    account = application.accounts.get_account(organisation_id, fetched.account_id)
    profile = application.business_profiles.get_profile(user_id)
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


@cli.command("stats")
@click.option("--user-id", type=int, required=True, help=_USER_ID_HELP)
@click.pass_obj
def stats(application: Application, user_id: int) -> None:
    result = application.stats.get_stats(_organisation_id(application, user_id))
    click.echo(f"Accounts: {result.account_count}")


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
