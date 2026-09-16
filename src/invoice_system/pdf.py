from datetime import date
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Account, BusinessProfile, Invoice, LineItem, Quote


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


def _text_lines(text: str | None) -> list[str]:
    """Splits free text into its non-blank lines, each individually
    stripped - shared by document_header_lines/document_footer_lines below.
    A blank line (just whitespace, or empty) is dropped rather than
    rendered as an empty Paragraph."""
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def document_header_lines(profile: BusinessProfile | None) -> list[str]:
    """The free text shown above the title on every quote/invoice PDF this
    user generates (see BusinessProfile.document_header) - deliberately not
    a per-page running header, just fixed text once at the top of the
    document (see BusinessProfile's docstring for why)."""
    return _text_lines(profile.document_header if profile is not None else None)


def document_footer_lines(profile: BusinessProfile | None) -> list[str]:
    """The free text shown below the totals table on every quote/invoice
    PDF this user generates (see BusinessProfile.document_footer) - same
    "fixed text once," not per-page, as document_header_lines above."""
    return _text_lines(profile.document_footer if profile is not None else None)


def _render(
    *,
    title: str,
    number: str,
    status: str,
    issue_date: date,
    due_or_expiry_label: str,
    due_or_expiry_date: date | None,
    account: Account,
    line_items: list[LineItem],
    currency: str,
    from_profile: BusinessProfile | None,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"{title} {number}")
    styles = getSampleStyleSheet()

    story = []
    header_lines = document_header_lines(from_profile)
    if header_lines:
        for line in header_lines:
            story.append(Paragraph(line, styles["Normal"]))
        story.append(Spacer(1, 8 * mm))

    story.extend(
        [
            Paragraph(f"{title} {number}", styles["Title"]),
            Paragraph(f"Status: {status}", styles["Normal"]),
            Paragraph(f"Issue date: {issue_date.isoformat()}", styles["Normal"]),
        ]
    )
    if due_or_expiry_date is not None:
        story.append(Paragraph(f"{due_or_expiry_label}: {due_or_expiry_date.isoformat()}", styles["Normal"]))
    story.append(Spacer(1, 8 * mm))

    from_lines = business_profile_lines(from_profile)
    if from_lines:
        story.append(Paragraph("From", styles["Heading3"]))
        for line in from_lines:
            story.append(Paragraph(line, styles["Normal"]))
        story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("Bill to", styles["Heading3"]))
    story.append(Paragraph(account.business_name, styles["Normal"]))
    if account.contact_name:
        story.append(Paragraph(account.contact_name, styles["Normal"]))
    for line in account_address_lines(account):
        story.append(Paragraph(line, styles["Normal"]))
    story.append(Paragraph(account.email, styles["Normal"]))
    story.append(Spacer(1, 8 * mm))

    table_data = [["Description", "Qty", "Unit price", "VAT", "Total"]]
    for item in line_items:
        table_data.append(
            [
                item.description,
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
            ]
        )
    )
    story.append(table)

    footer_lines = document_footer_lines(from_profile)
    if footer_lines:
        story.append(Spacer(1, 8 * mm))
        for line in footer_lines:
            story.append(Paragraph(line, styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()
