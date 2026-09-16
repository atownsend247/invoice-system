from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

_CENT = Decimal("0.01")


class QuoteStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONVERTED = "converted"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"


@dataclass
class Account:
    """A business we provide a service to and bill via quotes/invoices."""

    id: int | None
    business_name: str
    contact_name: str | None
    email: str
    phone: str | None
    address: str
    created_at: datetime


@dataclass
class BusinessProfile:
    """The logged-in user's own business details - not a domain "Account"
    (that's the client being billed) and not sessionkit's User (that's the
    login identity). One per user, keyed by sessionkit's user id - see
    CLAUDE.md for why that's a plain column, not an enforced foreign key.

    title/first_name/last_name are the account holder's own name (title is
    the only optional one of the three, e.g. "Mr"/"Dr" - a form nicety, not
    something anyone should be blocked from saving without). business_name
    is still required; the address fields are not (a sole trader may
    legally trade under their home address and not want it on every
    document, or simply not have filled it in yet) - each line is
    independently optional, not "all or nothing", to avoid inventing a
    cross-field validation rule nobody asked for.

    Address fields follow the UK GOV.UK Design System's standard address
    pattern (address_line1/2, town_or_city, county, postcode) rather than a
    single free-text field - see CLAUDE.md and data-model.md.

    currency is this user's *reporting* currency - the one the home
    dashboard's monthly totals are summed in (see
    InvoiceService.monthly_totals). It's independent of the currency chosen
    per quote/invoice (Quote.currency/Invoice.currency default to "USD" but
    are freely chosen at creation) - an invoice in a different currency than
    this setting is simply excluded from that report rather than
    naively summed into it. Defaults to "GBP"."""

    id: int | None
    user_id: int
    title: str | None
    first_name: str
    last_name: str
    business_name: str
    address_line1: str | None
    address_line2: str | None
    town_or_city: str | None
    county: str | None
    postcode: str | None
    payment_terms_days: int
    currency: str
    utr: str | None
    vat_number: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class LineItem:
    """tax_rate is a fraction (`Decimal("0.20")` for 20% VAT, `Decimal("0")`
    for none) applied to this line only - there's no invoice-wide rate,
    since different lines can legitimately carry different UK VAT rates
    (standard 20%/reduced 5%/zero 0%). `total` is *gross* (`net_total +
    tax_amount`) - the amount this line actually adds to what's owed; use
    `net_total`/`tax_amount` for the pre-tax amount and the tax alone."""

    id: int | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    position: int

    @property
    def net_total(self) -> Decimal:
        return self.quantity * self.unit_price

    @property
    def tax_amount(self) -> Decimal:
        # Rounded to the minor currency unit (cents/pence) - net_total * a
        # 2dp tax_rate otherwise carries extra decimal places (e.g.
        # 100.00 * 0.20 = 20.0000) that don't correspond to real money.
        return (self.net_total * self.tax_rate).quantize(_CENT, rounding=ROUND_HALF_UP)

    @property
    def total(self) -> Decimal:
        return self.net_total + self.tax_amount


@dataclass
class Quote:
    id: int | None
    account_id: int
    number: str | None
    status: QuoteStatus
    currency: str
    issue_date: date
    expiry_date: date | None
    created_at: datetime
    line_items: list[LineItem] = field(default_factory=list)

    @property
    def subtotal(self) -> Decimal:
        return sum((item.net_total for item in self.line_items), Decimal("0"))

    @property
    def tax_total(self) -> Decimal:
        return sum((item.tax_amount for item in self.line_items), Decimal("0"))

    @property
    def total(self) -> Decimal:
        return sum((item.total for item in self.line_items), Decimal("0"))


@dataclass
class Invoice:
    id: int | None
    account_id: int
    quote_id: int | None
    number: str | None
    status: InvoiceStatus
    currency: str
    issue_date: date
    due_date: date | None
    created_at: datetime
    line_items: list[LineItem] = field(default_factory=list)

    @property
    def subtotal(self) -> Decimal:
        return sum((item.net_total for item in self.line_items), Decimal("0"))

    @property
    def tax_total(self) -> Decimal:
        return sum((item.tax_amount for item in self.line_items), Decimal("0"))

    @property
    def total(self) -> Decimal:
        return sum((item.total for item in self.line_items), Decimal("0"))


@dataclass
class MonthlyInvoiceTotals:
    """One month's worth of invoice totals, split by paid vs not - see
    InvoiceService.monthly_totals. `month` is "YYYY-MM"."""

    month: str
    paid_total: Decimal
    unpaid_total: Decimal


@dataclass
class Stats:
    """All-time, system-wide counters for the home dashboard's stats
    section - see StatsService.get_stats. Deliberately a small, flat
    dataclass rather than one field per entity type growing organically -
    add fields here as new stats are actually asked for, not speculatively."""

    account_count: int
