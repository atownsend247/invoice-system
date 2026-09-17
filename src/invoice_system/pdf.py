from datetime import date
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Account, BusinessProfile, Expense, Invoice, LineItem, Quote


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
    parsing rendered PDF bytes - reportlab has no matching "read a PDF back"
    half to assert with."""
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


def _text_paragraph(text: str, style) -> Paragraph:
    """A `Paragraph` for free text that ultimately came from a user
    (business/account names, addresses, a line item description, document
    header/footer, bank details) - reportlab's `Paragraph` interprets a
    small subset of HTML-like markup in its text, so an unescaped
    `&`/`<`/`>` (all unremarkable in a real business name like "Smith &
    Sons" or a line item description) would corrupt the rendered output or
    crash `doc.build()` outright. Only needed for this reportlab-specific
    "how this gets drawn" concern - the pure line-selection functions
    above (business_profile_lines etc.) return plain, unescaped strings,
    which is what their own unit tests assert against."""
    return Paragraph(escape(text), style)


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
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"{title} {number}")
    styles = getSampleStyleSheet()

    story = []
    if header_lines:
        for line in header_lines:
            story.append(_text_paragraph(line, styles["Normal"]))
        story.append(Spacer(1, 8 * mm))

    story.extend(
        [
            Paragraph(f"{title} {number}", styles["Title"]),
            *([Paragraph(f"Status: {status}", styles["Normal"])] if status is not None else []),
            Paragraph(f"Issue date: {issue_date.isoformat()}", styles["Normal"]),
        ]
    )
    if due_or_expiry_date is not None:
        story.append(Paragraph(f"{due_or_expiry_label}: {due_or_expiry_date.isoformat()}", styles["Normal"]))
    story.append(Spacer(1, 8 * mm))

    bill_to_flowables = [
        Paragraph("Bill to", styles["Heading3"]),
        _text_paragraph(account.business_name, styles["Normal"]),
    ]
    if account.contact_name:
        bill_to_flowables.append(_text_paragraph(account.contact_name, styles["Normal"]))
    for line in account_address_lines(account):
        bill_to_flowables.append(_text_paragraph(line, styles["Normal"]))
    bill_to_flowables.append(_text_paragraph(account.email, styles["Normal"]))

    from_lines = business_profile_lines(from_profile)
    if from_lines:
        # From stays on the left where it's always been; Bill to moves to
        # sit alongside it on the right instead of stacking below it - a
        # single-row, two-column Table with each side's Paragraphs as a
        # cell's flowable list (not text - platypus table cells accept
        # either). Only done when there's a "From" to show at all: with no
        # business profile set, Bill to just stays exactly where it was
        # (top-left, right after the title/dates), same as before this
        # layout existed.
        from_flowables = [Paragraph("From", styles["Heading3"])]
        from_flowables.extend(_text_paragraph(line, styles["Normal"]) for line in from_lines)
        story.append(
            Table(
                [[from_flowables, bill_to_flowables]],
                colWidths=[85 * mm, 85 * mm],
                style=TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (0, 0), 10 * mm),  # gutter between the two columns
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                ),
            )
        )
    else:
        story.extend(bill_to_flowables)
    story.append(Spacer(1, 8 * mm))

    table_data = [["Description", "Qty", "Unit price", "VAT", "Total"]]
    for item in line_items:
        table_data.append(
            [
                # A Paragraph, not a plain string - a long description (e.g.
                # "Domain Registration - example.co.uk") needs to wrap
                # within the column instead of overflowing into "Qty"
                # (found from a real generated PDF, not just reasoning
                # about it). The other cells stay plain strings: short,
                # numeric-ish, and never user-authored free text, so
                # there's nothing for them to wrap or need escaping.
                _text_paragraph(item.description, styles["Normal"]),
                str(item.quantity),
                f"{item.unit_price} {currency}",
                f"{item.tax_rate:.0%}",
                f"{item.total} {currency}",
            ]
        )
    subtotal = sum((item.net_total for item in line_items), Decimal("0"))
    tax_total = sum((item.tax_amount for item in line_items), Decimal("0"))
    total = subtotal + tax_total
    summary_rows_from = len(table_data)
    table_data.append(["", "", "", "Subtotal", f"{subtotal} {currency}"])
    table_data.append(["", "", "", "VAT", f"{tax_total} {currency}"])
    table_data.append(["", "", "", "Total", f"{total} {currency}"])

    table = Table(table_data, colWidths=[65 * mm, 20 * mm, 30 * mm, 20 * mm, 35 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, summary_rows_from - 1), 0.25, colors.grey),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                # TOP, not the default - a wrapped multi-line description
                # would otherwise sit oddly against its row's other,
                # single-line cells.
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(table)

    if show_bank_details:
        bank_lines = bank_details_lines(from_profile)
        if bank_lines:
            story.append(Spacer(1, 8 * mm))
            story.append(Paragraph("Payment details", styles["Heading3"]))
            for line in bank_lines:
                story.append(_text_paragraph(line, styles["Normal"]))

    if footer_lines:
        story.append(Spacer(1, 8 * mm))
        for line in footer_lines:
            story.append(_text_paragraph(line, styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()
