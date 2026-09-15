from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


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
    single free-text field - see CLAUDE.md and data-model.md."""

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
    utr: str | None
    vat_number: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class LineItem:
    id: int | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    position: int

    @property
    def total(self) -> Decimal:
        return self.quantity * self.unit_price


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
    def total(self) -> Decimal:
        return sum((item.total for item in self.line_items), Decimal("0"))
