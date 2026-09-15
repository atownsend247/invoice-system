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
