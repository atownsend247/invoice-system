import math
import mimetypes
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import click

from ..auth import build_auth
from ..demo_data import DEMO_EMAIL, DEMO_PASSWORD, seed_demo_data
from ..errors import AppError
from ..factory import Application, build_application
from ..paths import DEFAULT_STORAGE_DIR, StoragePaths
from ..pdf import render_expense_pdf, render_invoice_pdf, render_quote_pdf

_USER_ID_HELP = (
    "sessionkit's User.id (see 'sessionkit list') - resolves which organisation's data to use "
    "(auto-created on first use per user, see CLAUDE.md); required since the CLI has no login "
    "session to infer it from."
)


def _organisation_id(application: Application, user_id: str) -> str:
    return application.organisations.get_or_create_for_user(user_id)


@click.group()
@click.option(
    "--storage-dir",
    default=DEFAULT_STORAGE_DIR,
    show_default=True,
    help="Base directory for all persistent data (databases, uploaded expense-attachment PDFs, and - "
    "reserved for future use - logs), grouped under db/ and attachments/ subdirectories - see "
    "CLAUDE.md. --db/--attachments-dir below override individual paths within it.",
)
@click.option(
    "--db",
    "db_path",
    default=None,
    help="Path to the domain SQLite database file. Defaults to <storage-dir>/db/invoice_system.db.",
)
@click.option(
    "--attachments-dir",
    default=None,
    help="Directory uploaded expense-attachment PDFs are stored in (see 'expense attachment add'). "
    "Defaults to <storage-dir>/attachments.",
)
@click.pass_context
def cli(ctx: click.Context, storage_dir: str, db_path: str | None, attachments_dir: str | None) -> None:
    paths = StoragePaths(storage_dir)
    if db_path is None:
        # Only touch disk for the derived default - an explicit --db
        # override means storage-dir's own db/ subdirectory is never
        # actually used, so nothing should create it (found the hard way:
        # doing this unconditionally left a stray empty storage/db/ in
        # every test run, even ones that override both --db and
        # --attachments-dir - see the matching guard in api/app.py's
        # lifespan and this repo's test fixtures).
        paths.ensure_db_dir()
    application = build_application(
        db_path or str(paths.domain_db_path),
        attachments_dir=attachments_dir or str(paths.attachments_dir),
    )
    ctx.call_on_close(application.close)
    ctx.obj = application
    # Click's `meta` dict, not `obj` - `obj` is the Application every
    # subcommand already receives via @click.pass_obj (100+ call sites);
    # only init-db additionally needs the resolved storage paths (to
    # default INVOICE_SYSTEM_AUTH_DB's own fallback), so that one command
    # alone reaches into `meta` via @click.pass_context instead.
    ctx.meta["storage_paths"] = paths


@cli.command("init-db")
@click.option(
    "--demo/--no-demo",
    default=True,
    show_default=True,
    help="Seed a demo login user, business profile, accounts, and a year of quotes/invoices "
    "in a mix of statuses. Safe to repeat - a no-op once the demo user already exists.",
)
@click.pass_context
def init_db(ctx: click.Context, demo: bool) -> None:
    application: Application = ctx.obj
    if not demo:
        click.echo("Database ready")
        return

    paths: StoragePaths = ctx.meta["storage_paths"]
    if "INVOICE_SYSTEM_AUTH_DB" not in os.environ:
        paths.ensure_db_dir()  # idempotent - a no-op if the cli() group already created it
    auth_db_path = os.environ.get("INVOICE_SYSTEM_AUTH_DB", str(paths.auth_db_path))
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
@click.option("--user-id", required=True, help=_USER_ID_HELP)
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
    user_id: str,
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
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.option("--page", default=1, show_default=True)
@click.option("--page-size", default=100, show_default=True, help="Max 200.")
@click.pass_obj
def account_list(application: Application, user_id: str, page: int, page_size: int) -> None:
    result = application.accounts.list_accounts(
        _organisation_id(application, user_id), page=page, page_size=page_size
    )
    for acc in result.items:
        click.echo(f"{acc.id}\t{acc.business_name}\t{acc.email}")
    click.echo(f"Page {page} of {max(1, math.ceil(result.total / page_size))} (total {result.total})")


@account.command("update")
@click.argument("account_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
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
    account_id: str,
    user_id: str,
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
def domain() -> None:
    pass


@domain.command("create")
@click.argument("account_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.option("--domain-name", required=True)
@click.option("--expiry-date", required=True, type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--registrar", required=True)
@click.option("--auto-renew/--no-auto-renew", default=False)
@click.pass_obj
def domain_create(
    application: Application,
    account_id: str,
    user_id: str,
    domain_name: str,
    expiry_date: datetime,
    registrar: str,
    auto_renew: bool,
) -> None:
    created = application.domains.create_domain(
        _organisation_id(application, user_id),
        account_id,
        domain_name=domain_name,
        expiry_date=expiry_date.date(),
        registrar=registrar,
        auto_renew=auto_renew,
    )
    click.echo(f"Created domain {created.id}: {created.domain_name}")


@domain.command("list")
@click.argument("account_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def domain_list(application: Application, account_id: str, user_id: str) -> None:
    for d in application.domains.list_domains(_organisation_id(application, user_id), account_id):
        auto = "auto-renew" if d.auto_renew else "manual renewal"
        click.echo(f"{d.id}\t{d.domain_name}\texpires {d.expiry_date}\t{d.registrar}\t{auto}")


@domain.command("update")
@click.argument("account_id")
@click.argument("domain_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.option("--domain-name", required=True)
@click.option("--expiry-date", required=True, type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--registrar", required=True)
@click.option("--auto-renew/--no-auto-renew", default=False)
@click.pass_obj
def domain_update(
    application: Application,
    account_id: str,
    domain_id: str,
    user_id: str,
    domain_name: str,
    expiry_date: datetime,
    registrar: str,
    auto_renew: bool,
) -> None:
    updated = application.domains.update_domain(
        _organisation_id(application, user_id),
        account_id,
        domain_id,
        domain_name=domain_name,
        expiry_date=expiry_date.date(),
        registrar=registrar,
        auto_renew=auto_renew,
    )
    click.echo(f"Updated domain {updated.id}: {updated.domain_name}")


@domain.command("delete")
@click.argument("account_id")
@click.argument("domain_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def domain_delete(application: Application, account_id: str, domain_id: str, user_id: str) -> None:
    application.domains.delete_domain(_organisation_id(application, user_id), account_id, domain_id)
    click.echo(f"Deleted domain {domain_id}")


@cli.group()
def registrar() -> None:
    pass


@registrar.command("create")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.option("--name", required=True)
@click.option("--notes", default=None)
@click.pass_obj
def registrar_create(application: Application, user_id: str, name: str, notes: str | None) -> None:
    created = application.registrars.create_registrar(
        _organisation_id(application, user_id), name=name, notes=notes
    )
    click.echo(f"Created registrar {created.id}: {created.name}")


@registrar.command("list")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def registrar_list(application: Application, user_id: str) -> None:
    for r in application.registrars.list_registrars(_organisation_id(application, user_id)):
        click.echo(f"{r.id}\t{r.name}\t{r.notes or '-'}")


@registrar.command("update")
@click.argument("registrar_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.option("--name", required=True)
@click.option("--notes", default=None)
@click.pass_obj
def registrar_update(
    application: Application, registrar_id: str, user_id: str, name: str, notes: str | None
) -> None:
    updated = application.registrars.update_registrar(
        _organisation_id(application, user_id), registrar_id, name=name, notes=notes
    )
    click.echo(f"Updated registrar {updated.id}: {updated.name}")


@registrar.command("delete")
@click.argument("registrar_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def registrar_delete(application: Application, registrar_id: str, user_id: str) -> None:
    application.registrars.delete_registrar(_organisation_id(application, user_id), registrar_id)
    click.echo(f"Deleted registrar {registrar_id}")


@cli.group()
def quote() -> None:
    pass


@quote.command("create")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.option("--account-id", required=True)
@click.option("--currency", default="USD", show_default=True)
@click.pass_obj
def quote_create(application: Application, user_id: str, account_id: str, currency: str) -> None:
    created = application.quotes.create_quote(
        organisation_id=_organisation_id(application, user_id), account_id=account_id, currency=currency
    )
    click.echo(f"Created quote {created.id} (draft)")


@quote.command("add-item")
@click.argument("quote_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
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
    quote_id: str,
    user_id: str,
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
@click.argument("quote_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def quote_send(application: Application, quote_id: str, user_id: str) -> None:
    sent = application.quotes.send(_organisation_id(application, user_id), quote_id)
    click.echo(f"Quote {quote_id} sent as {sent.number}")


@quote.command("convert")
@click.argument("quote_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def quote_convert(application: Application, quote_id: str, user_id: str) -> None:
    invoice = application.quotes.convert_to_invoice(_organisation_id(application, user_id), quote_id)
    click.echo(f"Converted quote {quote_id} to invoice {invoice.id}")


@quote.command("pdf")
@click.argument("quote_id")
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option(
    "--user-id",
    required=True,
    help=_USER_ID_HELP + " Also shown on the PDF as the 'From' party (see 'settings show'), if set.",
)
@click.pass_obj
def quote_pdf(application: Application, quote_id: str, output: str, user_id: str) -> None:
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
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.option("--account-id", default=None)
@click.option("--page", default=1, show_default=True)
@click.option("--page-size", default=100, show_default=True, help="Max 200.")
@click.pass_obj
def invoice_list(
    application: Application, user_id: str, account_id: str | None, page: int, page_size: int
) -> None:
    organisation_id = _organisation_id(application, user_id)
    result = application.invoices.list_invoices(
        organisation_id, account_id=account_id, page=page, page_size=page_size
    )
    for inv in result.items:
        click.echo(f"{inv.id}\t{inv.number or 'draft'}\t{inv.status.value}")
    click.echo(f"Page {page} of {max(1, math.ceil(result.total / page_size))} (total {result.total})")


@invoice.command("send")
@click.argument("invoice_id")
@click.option(
    "--user-id",
    required=True,
    help=_USER_ID_HELP + " Also uses this user's payment terms (see 'settings show') for the due date.",
)
@click.pass_obj
def invoice_send(application: Application, invoice_id: str, user_id: str) -> None:
    organisation_id = _organisation_id(application, user_id)
    payment_terms_days = application.business_profiles.get_profile(user_id).payment_terms_days
    sent = application.invoices.send(organisation_id, invoice_id, payment_terms_days=payment_terms_days)
    click.echo(f"Invoice {invoice_id} sent as {sent.number} (due {sent.due_date})")


@invoice.command("void")
@click.argument("invoice_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def invoice_void(application: Application, invoice_id: str, user_id: str) -> None:
    application.invoices.void(_organisation_id(application, user_id), invoice_id)
    click.echo(f"Invoice {invoice_id} voided")


@invoice.command("pay")
@click.argument("invoice_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def invoice_pay(application: Application, invoice_id: str, user_id: str) -> None:
    application.invoices.pay(_organisation_id(application, user_id), invoice_id)
    click.echo(f"Invoice {invoice_id} marked paid")


@invoice.command("monthly-totals")
@click.option(
    "--user-id",
    required=True,
    help=_USER_ID_HELP + " Also resolves this user's reporting currency (see 'settings show') - only "
    "invoices in that currency are counted.",
)
@click.pass_obj
def invoice_monthly_totals(application: Application, user_id: str) -> None:
    organisation_id = _organisation_id(application, user_id)
    profile = application.business_profiles.get_profile(user_id)
    for entry in application.invoices.monthly_totals(organisation_id, profile.currency):
        click.echo(
            f"{entry.month}\tpaid {entry.paid_total} {profile.currency}"
            f"\tunpaid {entry.unpaid_total} {profile.currency}"
        )


@invoice.command("pdf")
@click.argument("invoice_id")
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option(
    "--user-id",
    required=True,
    help=_USER_ID_HELP + " Also shown on the PDF as the 'From' party (see 'settings show'), if set.",
)
@click.pass_obj
def invoice_pdf(application: Application, invoice_id: str, output: str, user_id: str) -> None:
    organisation_id = _organisation_id(application, user_id)
    fetched = application.invoices.get_invoice(organisation_id, invoice_id)
    account = application.accounts.get_account(organisation_id, fetched.account_id)
    profile = application.business_profiles.get_profile(user_id)
    Path(output).write_bytes(render_invoice_pdf(account, fetched, profile))
    click.echo(f"Wrote {output}")


@cli.group()
def expense() -> None:
    pass


@expense.command("create")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.option("--account-id", required=True)
@click.option("--currency", default="USD", show_default=True)
@click.option(
    "--expense-date",
    default=None,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="When the expense actually happened, if different from today - see CLAUDE.md.",
)
@click.pass_obj
def expense_create(
    application: Application, user_id: str, account_id: str, currency: str, expense_date: datetime | None
) -> None:
    created = application.expenses.create_expense(
        organisation_id=_organisation_id(application, user_id),
        account_id=account_id,
        currency=currency,
        expense_date=expense_date.date() if expense_date else None,
    )
    click.echo(f"Created expense {created.id} ({created.number})")


@expense.command("list")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.option("--account-id", default=None)
@click.pass_obj
def expense_list(application: Application, user_id: str, account_id: str | None) -> None:
    organisation_id = _organisation_id(application, user_id)
    for exp in application.expenses.list_expenses(organisation_id, account_id=account_id):
        click.echo(f"{exp.id}\t{exp.number}\t{exp.total} {exp.currency}\texpense date {exp.expense_date}")


@expense.command("set-date")
@click.argument("expense_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.option("--expense-date", required=True, type=click.DateTime(formats=["%Y-%m-%d"]))
@click.pass_obj
def expense_set_date(application: Application, expense_id: str, user_id: str, expense_date: datetime) -> None:
    updated = application.expenses.update_expense_date(
        _organisation_id(application, user_id), expense_id, expense_date.date()
    )
    click.echo(f"Updated expense {updated.id}: expense date is now {updated.expense_date}")


@expense.command("monthly-totals")
@click.option(
    "--user-id",
    required=True,
    help=_USER_ID_HELP + " Also resolves this user's reporting currency (see 'settings show') - only "
    "expenses in that currency are counted.",
)
@click.pass_obj
def expense_monthly_totals(application: Application, user_id: str) -> None:
    organisation_id = _organisation_id(application, user_id)
    profile = application.business_profiles.get_profile(user_id)
    for entry in application.expenses.monthly_totals(organisation_id, profile.currency):
        click.echo(f"{entry.month}\t{entry.total} {profile.currency}")


@expense.command("add-item")
@click.argument("expense_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
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
def expense_add_item(
    application: Application,
    expense_id: str,
    user_id: str,
    description: str,
    quantity: Decimal,
    unit_price: Decimal,
    tax_rate: Decimal,
) -> None:
    application.expenses.add_line_item(
        _organisation_id(application, user_id),
        expense_id,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        tax_rate=tax_rate,
    )
    click.echo("Added line item")


@expense.command("pdf")
@click.argument("expense_id")
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option(
    "--user-id",
    required=True,
    help=_USER_ID_HELP + " Also shown on the PDF as the 'From' party (see 'settings show'), if set.",
)
@click.pass_obj
def expense_pdf(application: Application, expense_id: str, output: str, user_id: str) -> None:
    organisation_id = _organisation_id(application, user_id)
    fetched = application.expenses.get_expense(organisation_id, expense_id)
    account = application.accounts.get_account(organisation_id, fetched.account_id)
    profile = application.business_profiles.get_profile(user_id)
    Path(output).write_bytes(render_expense_pdf(account, fetched, profile))
    click.echo(f"Wrote {output}")


@expense.group("attachment")
def expense_attachment() -> None:
    pass


@expense_attachment.command("add")
@click.argument("expense_id")
@click.option(
    "--file",
    "file_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to a local PDF file to upload (e.g. a scanned receipt).",
)
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def expense_attachment_add(application: Application, expense_id: str, file_path: str, user_id: str) -> None:
    organisation_id = _organisation_id(application, user_id)
    path = Path(file_path)
    # Guessed from the extension, not hardcoded to "application/pdf" - a
    # real Content-Type here (not just trusting the --file argument's
    # implied intent) is what lets ExpenseService.add_attachment's PDF
    # check mean anything for the CLI too, same validation a browser
    # upload through the API goes through.
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    attachment = application.expenses.add_attachment(
        organisation_id,
        expense_id,
        filename=path.name,
        content_type=content_type,
        data=path.read_bytes(),
    )
    click.echo(f"Uploaded attachment {attachment.id}: {attachment.filename} ({attachment.size} bytes)")


@expense_attachment.command("list")
@click.argument("expense_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def expense_attachment_list(application: Application, expense_id: str, user_id: str) -> None:
    organisation_id = _organisation_id(application, user_id)
    expense = application.expenses.get_expense(organisation_id, expense_id)
    for attachment in expense.attachments:
        click.echo(f"{attachment.id}\t{attachment.filename}\t{attachment.size} bytes")


@expense_attachment.command("download")
@click.argument("expense_id")
@click.argument("attachment_id")
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def expense_attachment_download(
    application: Application, expense_id: str, attachment_id: str, output: str, user_id: str
) -> None:
    organisation_id = _organisation_id(application, user_id)
    _attachment, data = application.expenses.get_attachment_bytes(organisation_id, expense_id, attachment_id)
    Path(output).write_bytes(data)
    click.echo(f"Wrote {output}")


@expense_attachment.command("delete")
@click.argument("expense_id")
@click.argument("attachment_id")
@click.option("--user-id", required=True, help=_USER_ID_HELP)
@click.pass_obj
def expense_attachment_delete(
    application: Application, expense_id: str, attachment_id: str, user_id: str
) -> None:
    organisation_id = _organisation_id(application, user_id)
    application.expenses.delete_attachment(organisation_id, expense_id, attachment_id)
    click.echo(f"Deleted attachment {attachment_id}")


@cli.group()
def settings() -> None:
    pass


@settings.command("show")
@click.option("--user-id", required=True, help="sessionkit's User.id - see 'sessionkit list'.")
@click.pass_obj
def settings_show(application: Application, user_id: str) -> None:
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
    click.echo(f"Bank account name: {profile.bank_account_name or '-'}")
    click.echo(f"Bank sort code: {profile.bank_sort_code or '-'}")
    click.echo(f"Bank account number: {profile.bank_account_number or '-'}")
    click.echo(f"Quote header: {profile.quote_document_header or '-'}")
    click.echo(f"Quote footer: {profile.quote_document_footer or '-'}")
    click.echo(f"Invoice header: {profile.invoice_document_header or '-'}")
    click.echo(f"Invoice footer: {profile.invoice_document_footer or '-'}")
    click.echo(f"Expense header: {profile.expense_document_header or '-'}")
    click.echo(f"Expense footer: {profile.expense_document_footer or '-'}")
    click.echo(f"Accent colour: {profile.accent_color or '-'}")


@settings.command("set")
@click.option("--user-id", required=True, help="sessionkit's User.id - see 'sessionkit list'.")
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
@click.option("--bank-account-name", default=None)
@click.option("--bank-sort-code", default=None)
@click.option("--bank-account-number", default=None)
@click.option("--quote-header", default=None, help="Free text (multi-line OK) shown above every quote PDF.")
@click.option("--quote-footer", default=None, help="Free text (multi-line OK) shown below every quote PDF.")
@click.option(
    "--invoice-header", default=None, help="Free text (multi-line OK) shown above every invoice PDF."
)
@click.option(
    "--invoice-footer", default=None, help="Free text (multi-line OK) shown below every invoice PDF."
)
@click.option(
    "--expense-header", default=None, help="Free text (multi-line OK) shown above every expense PDF."
)
@click.option(
    "--expense-footer", default=None, help="Free text (multi-line OK) shown below every expense PDF."
)
@click.option(
    "--accent-color",
    default=None,
    help="Brand colour used across every quote/invoice/expense PDF, as #RRGGBB.",
)
@click.pass_obj
def settings_set(
    application: Application,
    user_id: str,
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
    bank_account_name: str | None,
    bank_sort_code: str | None,
    bank_account_number: str | None,
    quote_header: str | None,
    quote_footer: str | None,
    invoice_header: str | None,
    invoice_footer: str | None,
    expense_header: str | None,
    expense_footer: str | None,
    accent_color: str | None,
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
        bank_account_name=bank_account_name,
        bank_sort_code=bank_sort_code,
        bank_account_number=bank_account_number,
        quote_document_header=quote_header,
        quote_document_footer=quote_footer,
        invoice_document_header=invoice_header,
        invoice_document_footer=invoice_footer,
        expense_document_header=expense_header,
        expense_document_footer=expense_footer,
        accent_color=accent_color,
    )
    click.echo(f"Saved business profile for user {user_id}")


@cli.command("stats")
@click.option(
    "--user-id",
    required=True,
    help=_USER_ID_HELP + " Also resolves this user's reporting currency (see 'settings show') - only "
    "paid invoices in that currency count toward total paid.",
)
@click.pass_obj
def stats(application: Application, user_id: str) -> None:
    organisation_id = _organisation_id(application, user_id)
    profile = application.business_profiles.get_profile(user_id)
    result = application.stats.get_stats(organisation_id, profile.currency)
    click.echo(f"Accounts: {result.account_count}")
    click.echo(
        f"Quotes: {result.quote_count} "
        f"({result.quotes_sent_count} sent, {result.quotes_converted_count} converted)"
    )
    click.echo(f"Invoices: {result.invoice_count}")
    click.echo(f"Total paid: {result.total_paid} {profile.currency}")


@cli.group()
def invite() -> None:
    pass


@invite.command("create")
@click.option(
    "--expires-in-days",
    default=7,
    show_default=True,
    help="How many days the invite stays valid for - it's also single-use, consumed on the first "
    "successful registration regardless of this expiry.",
)
@click.pass_obj
def invite_create(application: Application, expires_in_days: int) -> None:
    created = application.registration_invites.create_invite(expires_in_days=expires_in_days)
    click.echo(f"Created invite {created.token} (expires {created.expires_at.isoformat()})")
    click.echo(f"Registration link: /register?token={created.token}")


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
