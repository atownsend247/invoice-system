from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, field_validator


def _validate_decimal_string(value: str) -> str:
    try:
        Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{value!r} is not a valid decimal string") from exc
    return value


class AccountIn(BaseModel):
    business_name: str
    email: str
    address: str
    contact_name: str | None = None
    phone: str | None = None


class AccountOut(BaseModel):
    id: int
    business_name: str
    contact_name: str | None
    email: str
    phone: str | None
    address: str
    created_at: datetime

    @classmethod
    def from_model(cls, account) -> "AccountOut":
        return cls(
            id=account.id,
            business_name=account.business_name,
            contact_name=account.contact_name,
            email=account.email,
            phone=account.phone,
            address=account.address,
            created_at=account.created_at,
        )


class LineItemIn(BaseModel):
    description: str
    quantity: str
    unit_price: str
    tax_rate: str = "0"

    _validate_quantity = field_validator("quantity")(_validate_decimal_string)
    _validate_unit_price = field_validator("unit_price")(_validate_decimal_string)
    _validate_tax_rate = field_validator("tax_rate")(_validate_decimal_string)


class LineItemOut(BaseModel):
    id: int
    description: str
    quantity: str
    unit_price: str
    tax_rate: str
    net_total: str
    tax_amount: str
    total: str

    @classmethod
    def from_model(cls, item) -> "LineItemOut":
        return cls(
            id=item.id,
            description=item.description,
            quantity=str(item.quantity),
            unit_price=str(item.unit_price),
            tax_rate=str(item.tax_rate),
            net_total=str(item.net_total),
            tax_amount=str(item.tax_amount),
            total=str(item.total),
        )


class QuoteCreateIn(BaseModel):
    account_id: int
    currency: str = "USD"
    expiry_date: date | None = None


class QuoteOut(BaseModel):
    id: int
    account_id: int
    number: str | None
    status: str
    currency: str
    issue_date: date
    expiry_date: date | None
    created_at: datetime
    line_items: list[LineItemOut]
    subtotal: str
    tax_total: str
    total: str

    @classmethod
    def from_model(cls, quote) -> "QuoteOut":
        return cls(
            id=quote.id,
            account_id=quote.account_id,
            number=quote.number,
            status=quote.status.value,
            currency=quote.currency,
            issue_date=quote.issue_date,
            expiry_date=quote.expiry_date,
            created_at=quote.created_at,
            line_items=[LineItemOut.from_model(item) for item in quote.line_items],
            subtotal=str(quote.subtotal),
            tax_total=str(quote.tax_total),
            total=str(quote.total),
        )


class InvoiceOut(BaseModel):
    id: int
    account_id: int
    quote_id: int | None
    number: str | None
    status: str
    currency: str
    issue_date: date
    due_date: date | None
    created_at: datetime
    line_items: list[LineItemOut]
    subtotal: str
    tax_total: str
    total: str

    @classmethod
    def from_model(cls, invoice) -> "InvoiceOut":
        return cls(
            id=invoice.id,
            account_id=invoice.account_id,
            quote_id=invoice.quote_id,
            number=invoice.number,
            status=invoice.status.value,
            currency=invoice.currency,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            created_at=invoice.created_at,
            line_items=[LineItemOut.from_model(item) for item in invoice.line_items],
            subtotal=str(invoice.subtotal),
            tax_total=str(invoice.tax_total),
            total=str(invoice.total),
        )


class BusinessProfileIn(BaseModel):
    first_name: str
    last_name: str
    business_name: str
    title: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    town_or_city: str | None = None
    county: str | None = None
    postcode: str | None = None
    payment_terms_days: int = 30
    currency: str = "GBP"
    utr: str | None = None
    vat_number: str | None = None


class BusinessProfileOut(BaseModel):
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
    updated_at: datetime

    @classmethod
    def from_model(cls, profile) -> "BusinessProfileOut":
        return cls(
            title=profile.title,
            first_name=profile.first_name,
            last_name=profile.last_name,
            business_name=profile.business_name,
            address_line1=profile.address_line1,
            address_line2=profile.address_line2,
            town_or_city=profile.town_or_city,
            county=profile.county,
            postcode=profile.postcode,
            payment_terms_days=profile.payment_terms_days,
            currency=profile.currency,
            utr=profile.utr,
            vat_number=profile.vat_number,
            updated_at=profile.updated_at,
        )


class MonthlyInvoiceTotalOut(BaseModel):
    month: str
    paid_total: str
    unpaid_total: str

    @classmethod
    def from_model(cls, entry) -> "MonthlyInvoiceTotalOut":
        return cls(month=entry.month, paid_total=str(entry.paid_total), unpaid_total=str(entry.unpaid_total))


class MonthlyTotalsReportOut(BaseModel):
    currency: str
    months: list[MonthlyInvoiceTotalOut]

    @classmethod
    def from_models(cls, currency: str, entries) -> "MonthlyTotalsReportOut":
        return cls(currency=currency, months=[MonthlyInvoiceTotalOut.from_model(e) for e in entries])


class StatsOut(BaseModel):
    account_count: int

    @classmethod
    def from_model(cls, stats) -> "StatsOut":
        return cls(account_count=stats.account_count)
