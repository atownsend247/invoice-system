from datetime import date
from decimal import Decimal

import jinja2
import weasyprint

from .models import Account, BusinessProfile, Expense, Invoice, LineItem, Quote

# The brand colour used across every quote/invoice/expense PDF a user
# generates when BusinessProfile.accent_color is unset - a neutral, dark
# near-black rather than presuming any particular brand colour, so a PDF
# still looks finished before anyone visits Settings (see
# BusinessProfile.accent_color's docstring).
_ACCENT_FALLBACK = "#1F2430"

# Rendered once at import time, not per-call - a jinja2.Environment is
# meant to be reused (it caches compiled templates). autoescape=True is
# what keeps every free-text value (business/account names, addresses, a
# line item description, document header/footer lines) HTML-safe when
# interpolated into document.html.jinja below - the reportlab version of
# this module needed a hand-rolled escape() helper for the same reason
# (Paragraph's own markup parsing); Jinja2's autoescaping replaces that
# entirely; there's nothing bespoke left to remember to call per value.
_env = jinja2.Environment(
    loader=jinja2.PackageLoader("invoice_system", "templates"),
    autoescape=True,
)
_template = _env.get_template("document.html.jinja")


def render_quote_pdf(account: Account, quote: Quote, from_profile: BusinessProfile | None = None) -> bytes:
    return _render(
        title="Quote",
        number=quote.number or f"DRAFT-{quote.id}",
        status=quote.status.value,
        issue_date=quote.issue_date,
        due_or_expiry_label="Expiry date",
        due_or_expiry_date=quote.expiry_date,
        account=account,
        line_items=quote.line_items,
        currency=quote.currency,
        from_profile=from_profile,
        header_lines=quote_header_lines(from_profile),
        footer_lines=quote_footer_lines(from_profile),
    )


def render_invoice_pdf(
    account: Account, invoice: Invoice, from_profile: BusinessProfile | None = None
) -> bytes:
    return _render(
        title="Invoice",
        number=invoice.number or f"DRAFT-{invoice.id}",
        status=invoice.status.value,
        issue_date=invoice.issue_date,
        due_or_expiry_label="Due date",
        due_or_expiry_date=invoice.due_date,
        account=account,
        line_items=invoice.line_items,
        currency=invoice.currency,
        from_profile=from_profile,
        header_lines=invoice_header_lines(from_profile),
        footer_lines=invoice_footer_lines(from_profile),
        # Bank details are only ever useful on an actual invoice - there's
        # nothing to pay yet against a quote, and an expense is a record of
        # money already spent, not something billed to the account (see
        # models.Expense) - so this is the one place `show_bank_details`
        # is True.
        show_bank_details=True,
        # customer_notes is an Invoice-only field (see models.Invoice) -
        # captured optionally when converting from a quote, editable
        # afterwards - there's nothing to split into lines beyond what
        # _text_lines already does for header/footer.
        customer_notes_lines=_text_lines(invoice.customer_notes),
    )


def render_expense_pdf(
    account: Account, expense: Expense, from_profile: BusinessProfile | None = None
) -> bytes:
    # No status - unlike Quote/Invoice, an Expense has no draft/sent
    # lifecycle (see models.Expense/CLAUDE.md), so there's nothing
    # meaningful to print on a "Status:" line; _render omits it entirely
    # when status is None rather than printing a fake constant. No
    # due/expiry date either, for the same reason.
    return _render(
        title="Expense",
        number=expense.number,
        status=None,
        issue_date=expense.issue_date,
        due_or_expiry_label="",
        due_or_expiry_date=None,
        account=account,
        line_items=expense.line_items,
        currency=expense.currency,
        from_profile=from_profile,
        header_lines=expense_header_lines(from_profile),
        footer_lines=expense_footer_lines(from_profile),
    )


def business_profile_lines(profile: BusinessProfile | None) -> list[str]:
    """What the "From" section shows: business name and address, if set -
    never the account holder's personal name (see CLAUDE.md). Address lines
    are each independently optional (see BusinessProfile), so this just
    prints whichever ones are actually set, in the standard UK order.
    Pulled out as a pure function so the decision (what shows, in what
    order, when there's nothing to show at all) is unit-testable without
    parsing rendered PDF bytes - there's no PDF-content-extraction library
    in use here to assert against the rendered output directly."""
    if profile is None or not profile.business_name.strip():
        return []
    address_fields = (
        profile.address_line1,
        profile.address_line2,
        profile.town_or_city,
        profile.county,
        profile.postcode,
    )
    return [profile.business_name, *(field for field in address_fields if field and field.strip())]


def account_address_lines(account: Account) -> list[str]:
    """The "Bill to" section's address lines - `address_line1` is always
    present (required, see models.Account), the rest each independently
    optional, same filtering as `business_profile_lines` above."""
    address_fields = (account.address_line2, account.town_or_city, account.county, account.postcode)
    return [account.address_line1, *(field for field in address_fields if field and field.strip())]


def bank_details_lines(profile: BusinessProfile | None) -> list[str]:
    """The "Payment details" section shown on generated invoices only,
    never quotes or expenses (see render_invoice_pdf) - bank_account_name/
    bank_sort_code/bank_account_number are each independently optional
    (see BusinessProfile), so this just prints whichever ones are actually
    set, same "print whichever ones exist" pattern as
    business_profile_lines/account_address_lines above. Pulled out as a
    pure function for the same reason those are."""
    if profile is None:
        return []
    fields = (
        ("Account name", profile.bank_account_name),
        ("Sort code", profile.bank_sort_code),
        ("Account number", profile.bank_account_number),
    )
    return [f"{label}: {value}" for label, value in fields if value and value.strip()]


def _text_lines(text: str | None) -> list[str]:
    """Splits free text into its non-blank lines, each individually
    stripped - shared by quote_header_lines/quote_footer_lines and their
    invoice_/expense_ equivalents below. A blank line (just whitespace, or
    empty) is dropped rather than
    rendered as an empty Paragraph."""
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def quote_header_lines(profile: BusinessProfile | None) -> list[str]:
    """The free text shown above the title on every quote PDF this user
    generates (see BusinessProfile.quote_document_header) - deliberately
    not a per-page running header, just fixed text once at the top of the
    document (see BusinessProfile's docstring for why). One independent
    pair per document type - see invoice_header_lines/expense_header_lines
    below - so each can say something different."""
    return _text_lines(profile.quote_document_header if profile is not None else None)


def quote_footer_lines(profile: BusinessProfile | None) -> list[str]:
    """The free text shown below the totals table on every quote PDF this
    user generates (see BusinessProfile.quote_document_footer) - same
    "fixed text once," not per-page, as quote_header_lines above."""
    return _text_lines(profile.quote_document_footer if profile is not None else None)


def invoice_header_lines(profile: BusinessProfile | None) -> list[str]:
    """Same as quote_header_lines, for invoices - see
    BusinessProfile.invoice_document_header."""
    return _text_lines(profile.invoice_document_header if profile is not None else None)


def invoice_footer_lines(profile: BusinessProfile | None) -> list[str]:
    """Same as quote_footer_lines, for invoices - see
    BusinessProfile.invoice_document_footer."""
    return _text_lines(profile.invoice_document_footer if profile is not None else None)


def expense_header_lines(profile: BusinessProfile | None) -> list[str]:
    """Same as quote_header_lines, for expenses - see
    BusinessProfile.expense_document_header."""
    return _text_lines(profile.expense_document_header if profile is not None else None)


def expense_footer_lines(profile: BusinessProfile | None) -> list[str]:
    """Same as quote_footer_lines, for expenses - see
    BusinessProfile.expense_document_footer."""
    return _text_lines(profile.expense_document_footer if profile is not None else None)


def _lighten(hex_color: str, amount: float) -> str:
    """Blends `hex_color` towards white by `amount` (0-1) - used for the
    status pill and totals-row backgrounds, which want a pale tint of the
    accent colour rather than the full-strength colour itself. Computed in
    Python rather than via CSS (e.g. `color-mix()`) since that's a very
    recent CSS Color Module 5 feature WeasyPrint's CSS support can't be
    assumed to cover - plain RGB arithmetic works everywhere."""
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    r, g, b = (round(c + (255 - c) * amount) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _money(amount: Decimal, currency: str) -> str:
    return f"{amount} {currency}"


def _render(
    *,
    title: str,
    number: str,
    status: str | None,
    issue_date: date,
    due_or_expiry_label: str,
    due_or_expiry_date: date | None,
    account: Account,
    line_items: list[LineItem],
    currency: str,
    from_profile: BusinessProfile | None,
    header_lines: list[str],
    footer_lines: list[str],
    show_bank_details: bool = False,
    customer_notes_lines: list[str] | None = None,
) -> bytes:
    accent = (from_profile.accent_color if from_profile is not None else None) or _ACCENT_FALLBACK

    subtotal = sum((item.net_total for item in line_items), Decimal("0"))
    tax_total = sum((item.tax_amount for item in line_items), Decimal("0"))
    total = subtotal + tax_total

    bank_lines = bank_details_lines(from_profile) if show_bank_details else []

    html = _template.render(
        title=title,
        number=number,
        status=status,
        issue_date=issue_date.isoformat(),
        due_or_expiry_label=due_or_expiry_label,
        due_or_expiry_date=due_or_expiry_date.isoformat() if due_or_expiry_date is not None else None,
        header_lines=header_lines,
        footer_lines=footer_lines,
        from_lines=business_profile_lines(from_profile),
        bill_to_name=account.business_name,
        bill_to_contact_name=account.contact_name,
        bill_to_address_lines=account_address_lines(account),
        bill_to_email=account.email,
        line_items=[
            {
                "description": item.description,
                "quantity": str(item.quantity),
                "unit_price": _money(item.unit_price, currency),
                "tax_rate": f"{item.tax_rate:.0%}",
                "total": _money(item.total, currency),
            }
            for item in line_items
        ],
        subtotal=_money(subtotal, currency),
        tax_total=_money(tax_total, currency),
        total=_money(total, currency),
        bank_lines=bank_lines,
        customer_notes_lines=customer_notes_lines or [],
        accent=accent,
        accent_tint=_lighten(accent, 0.9),
    )
    return weasyprint.HTML(string=html, base_url=None).write_pdf()
