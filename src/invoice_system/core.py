from datetime import date as date_
from datetime import timedelta
from decimal import Decimal

from .clock import Clock, system_clock
from .errors import InvalidTransition, NotFound, ValidationFailed
from .models import (
    Account,
    BusinessProfile,
    Invoice,
    InvoiceStatus,
    LineItem,
    MonthlyInvoiceTotals,
    Organisation,
    Quote,
    QuoteStatus,
    Stats,
)
from .repository import Repository

DEFAULT_INVOICE_DUE_DAYS = 30
DEFAULT_PAYMENT_TERMS_DAYS = 30
DEFAULT_CURRENCY = "GBP"
MONTHLY_TOTALS_MONTHS = 12
DEFAULT_ORGANISATION_NAME = "My Organisation"


class OrganisationService:
    """Resolves the tenant boundary for a login user - see
    models.py's Organisation docstring and CLAUDE.md's "Three separate
    things" (now four) section. Every Account/Quote/Invoice belongs to
    exactly one Organisation; `get_or_create_for_user` is how the API/CLI
    layers turn "which sessionkit user is this" into "which
    organisation's data can they see" before calling into
    AccountService/QuoteService/InvoiceService/StatsService, all of which
    take an `organisation_id` and never resolve one themselves."""

    def __init__(self, repository: Repository, clock: Clock = system_clock) -> None:
        self._repository = repository
        self._clock = clock

    def get_or_create_for_user(self, user_id: int, *, default_name: str = DEFAULT_ORGANISATION_NAME) -> int:
        existing = self._repository.get_organisation_id_for_user(user_id)
        if existing is not None:
            return existing
        organisation = self._repository.create_organisation(
            Organisation(id=None, name=default_name, created_at=self._clock())
        )
        return self._repository.add_organisation_member(organisation.id, user_id)


class AccountService:
    def __init__(self, repository: Repository, clock: Clock = system_clock) -> None:
        self._repository = repository
        self._clock = clock

    def create_account(
        self,
        *,
        organisation_id: int,
        business_name: str,
        email: str,
        address_line1: str,
        contact_name: str | None = None,
        phone: str | None = None,
        address_line2: str | None = None,
        town_or_city: str | None = None,
        county: str | None = None,
        postcode: str | None = None,
    ) -> Account:
        if not business_name.strip():
            raise ValidationFailed("business_name is required")
        if not email.strip():
            raise ValidationFailed("email is required")
        if not address_line1.strip():
            raise ValidationFailed("address_line1 is required")
        account = Account(
            id=None,
            organisation_id=organisation_id,
            business_name=business_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            address_line1=address_line1,
            address_line2=_blank_to_none(address_line2),
            town_or_city=_blank_to_none(town_or_city),
            county=_blank_to_none(county),
            postcode=_blank_to_none(postcode),
            created_at=self._clock(),
        )
        return self._repository.create_account(account)

    def get_account(self, organisation_id: int, account_id: int) -> Account:
        account = self._repository.get_account(organisation_id, account_id)
        if account is None:
            raise NotFound(f"account {account_id} not found")
        return account

    def list_accounts(self, organisation_id: int) -> list[Account]:
        return self._repository.list_accounts(organisation_id)

    def update_account(
        self,
        organisation_id: int,
        account_id: int,
        *,
        business_name: str,
        email: str,
        address_line1: str,
        contact_name: str | None = None,
        phone: str | None = None,
        address_line2: str | None = None,
        town_or_city: str | None = None,
        county: str | None = None,
        postcode: str | None = None,
    ) -> Account:
        existing = self.get_account(organisation_id, account_id)
        if not business_name.strip():
            raise ValidationFailed("business_name is required")
        if not email.strip():
            raise ValidationFailed("email is required")
        if not address_line1.strip():
            raise ValidationFailed("address_line1 is required")
        existing.business_name = business_name
        existing.contact_name = contact_name
        existing.email = email
        existing.phone = phone
        existing.address_line1 = address_line1
        existing.address_line2 = _blank_to_none(address_line2)
        existing.town_or_city = _blank_to_none(town_or_city)
        existing.county = _blank_to_none(county)
        existing.postcode = _blank_to_none(postcode)
        return self._repository.update_account(existing)


def _blank_to_none(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _month_start(d: date_) -> date_:
    return date_(d.year, d.month, 1)


def _month_key(d: date_) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _previous_month(d: date_) -> date_:
    return date_(d.year - 1, 12, 1) if d.month == 1 else date_(d.year, d.month - 1, 1)


def _validate_tax_rate(tax_rate: Decimal) -> None:
    if not (Decimal("0") <= tax_rate <= Decimal("1")):
        raise ValidationFailed("tax_rate must be between 0 and 1")


class BusinessProfileService:
    """The logged-in user's own details (name/address/payment terms/UTR/VAT/
    bank details/document header & footer), one per user - see CLAUDE.md
    for why this is deliberately not an `Account` (that's the client being
    billed) and not part of sessionkit. Deliberately still per-*user*, not
    per-Organisation, even after Organisation was introduced - see
    CLAUDE.md."""

    def __init__(self, repository: Repository, clock: Clock = system_clock) -> None:
        self._repository = repository
        self._clock = clock

    def get_profile(self, user_id: int) -> BusinessProfile:
        existing = self._repository.get_business_profile(user_id)
        if existing is not None:
            return existing
        now = self._clock()
        return BusinessProfile(
            id=None,
            user_id=user_id,
            title=None,
            first_name="",
            last_name="",
            business_name="",
            address_line1=None,
            address_line2=None,
            town_or_city=None,
            county=None,
            postcode=None,
            payment_terms_days=DEFAULT_PAYMENT_TERMS_DAYS,
            currency=DEFAULT_CURRENCY,
            utr=None,
            vat_number=None,
            bank_account_name=None,
            bank_sort_code=None,
            bank_account_number=None,
            document_header=None,
            document_footer=None,
            created_at=now,
            updated_at=now,
        )

    def save_profile(
        self,
        user_id: int,
        *,
        first_name: str,
        last_name: str,
        business_name: str,
        payment_terms_days: int,
        title: str | None = None,
        address_line1: str | None = None,
        address_line2: str | None = None,
        town_or_city: str | None = None,
        county: str | None = None,
        postcode: str | None = None,
        currency: str = DEFAULT_CURRENCY,
        utr: str | None = None,
        vat_number: str | None = None,
        bank_account_name: str | None = None,
        bank_sort_code: str | None = None,
        bank_account_number: str | None = None,
        document_header: str | None = None,
        document_footer: str | None = None,
    ) -> BusinessProfile:
        if not first_name.strip():
            raise ValidationFailed("first_name is required")
        if not last_name.strip():
            raise ValidationFailed("last_name is required")
        if not business_name.strip():
            raise ValidationFailed("business_name is required")
        if payment_terms_days <= 0:
            raise ValidationFailed("payment_terms_days must be a positive number of days")
        if not currency.strip():
            raise ValidationFailed("currency is required")

        existing = self._repository.get_business_profile(user_id)
        created_at = existing.created_at if existing is not None else self._clock()
        profile = BusinessProfile(
            id=existing.id if existing is not None else None,
            user_id=user_id,
            title=_blank_to_none(title),
            first_name=first_name,
            last_name=last_name,
            business_name=business_name,
            address_line1=_blank_to_none(address_line1),
            address_line2=_blank_to_none(address_line2),
            town_or_city=_blank_to_none(town_or_city),
            county=_blank_to_none(county),
            postcode=_blank_to_none(postcode),
            payment_terms_days=payment_terms_days,
            currency=currency.strip().upper(),
            utr=_blank_to_none(utr),
            vat_number=_blank_to_none(vat_number),
            bank_account_name=_blank_to_none(bank_account_name),
            bank_sort_code=_blank_to_none(bank_sort_code),
            bank_account_number=_blank_to_none(bank_account_number),
            document_header=_blank_to_none(document_header),
            document_footer=_blank_to_none(document_footer),
            created_at=created_at,
            updated_at=self._clock(),
        )
        return self._repository.upsert_business_profile(profile)


class QuoteService:
    def __init__(self, repository: Repository, clock: Clock = system_clock) -> None:
        self._repository = repository
        self._clock = clock

    def create_quote(
        self,
        *,
        organisation_id: int,
        account_id: int,
        currency: str = "USD",
        expiry_date: date_ | None = None,
    ) -> Quote:
        if self._repository.get_account(organisation_id, account_id) is None:
            raise NotFound(f"account {account_id} not found")
        quote = Quote(
            id=None,
            organisation_id=organisation_id,
            account_id=account_id,
            number=None,
            status=QuoteStatus.DRAFT,
            currency=currency,
            issue_date=self._clock().date(),
            expiry_date=expiry_date,
            created_at=self._clock(),
        )
        return self._repository.create_quote(quote)

    def get_quote(self, organisation_id: int, quote_id: int) -> Quote:
        return self._get_quote(organisation_id, quote_id)

    def list_quotes(self, organisation_id: int, account_id: int | None = None) -> list[Quote]:
        return self._repository.list_quotes(organisation_id, account_id=account_id)

    def add_line_item(
        self,
        organisation_id: int,
        quote_id: int,
        *,
        description: str,
        quantity: Decimal,
        unit_price: Decimal,
        tax_rate: Decimal = Decimal("0"),
    ) -> Quote:
        quote = self._get_draft_quote(organisation_id, quote_id)
        if not description.strip():
            raise ValidationFailed("description is required")
        _validate_tax_rate(tax_rate)
        item = LineItem(
            id=None,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            tax_rate=tax_rate,
            position=len(quote.line_items),
        )
        self._repository.add_quote_line_item(quote_id, item)
        return self._get_quote(organisation_id, quote_id)

    def send(self, organisation_id: int, quote_id: int) -> Quote:
        quote = self._get_quote(organisation_id, quote_id)
        if quote.status != QuoteStatus.DRAFT:
            raise InvalidTransition(f"quote {quote_id} is not a draft (status={quote.status.value})")
        if not quote.line_items:
            raise ValidationFailed(f"quote {quote_id} has no line items")
        quote.number = self._repository.next_quote_number(organisation_id)
        quote.status = QuoteStatus.SENT
        return self._repository.update_quote(quote)

    def mark_accepted(self, organisation_id: int, quote_id: int) -> Quote:
        return self._transition(
            organisation_id, quote_id, from_status=QuoteStatus.SENT, to_status=QuoteStatus.ACCEPTED
        )

    def mark_rejected(self, organisation_id: int, quote_id: int) -> Quote:
        return self._transition(
            organisation_id, quote_id, from_status=QuoteStatus.SENT, to_status=QuoteStatus.REJECTED
        )

    def mark_expired(self, organisation_id: int, quote_id: int) -> Quote:
        return self._transition(
            organisation_id, quote_id, from_status=QuoteStatus.SENT, to_status=QuoteStatus.EXPIRED
        )

    def convert_to_invoice(self, organisation_id: int, quote_id: int) -> Invoice:
        quote = self._get_quote(organisation_id, quote_id)
        if quote.status not in (QuoteStatus.SENT, QuoteStatus.ACCEPTED):
            raise InvalidTransition(f"quote {quote_id} cannot be converted from status {quote.status.value}")
        invoice = Invoice(
            id=None,
            organisation_id=organisation_id,
            account_id=quote.account_id,
            quote_id=quote.id,
            number=None,
            status=InvoiceStatus.DRAFT,
            currency=quote.currency,
            issue_date=self._clock().date(),
            due_date=None,
            created_at=self._clock(),
        )
        invoice = self._repository.create_invoice(invoice)
        for item in quote.line_items:
            self._repository.add_invoice_line_item(
                invoice.id,
                LineItem(
                    id=None,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    tax_rate=item.tax_rate,
                    position=item.position,
                ),
            )
        quote.status = QuoteStatus.CONVERTED
        self._repository.update_quote(quote)
        return self._repository.get_invoice(organisation_id, invoice.id)

    def _transition(
        self, organisation_id: int, quote_id: int, *, from_status: QuoteStatus, to_status: QuoteStatus
    ) -> Quote:
        quote = self._get_quote(organisation_id, quote_id)
        if quote.status != from_status:
            raise InvalidTransition(
                f"quote {quote_id} must be {from_status.value} to become {to_status.value} "
                f"(status={quote.status.value})"
            )
        quote.status = to_status
        return self._repository.update_quote(quote)

    def _get_quote(self, organisation_id: int, quote_id: int) -> Quote:
        quote = self._repository.get_quote(organisation_id, quote_id)
        if quote is None:
            raise NotFound(f"quote {quote_id} not found")
        return quote

    def _get_draft_quote(self, organisation_id: int, quote_id: int) -> Quote:
        quote = self._get_quote(organisation_id, quote_id)
        if quote.status != QuoteStatus.DRAFT:
            raise InvalidTransition(f"quote {quote_id} is not editable (status={quote.status.value})")
        return quote


class InvoiceService:
    def __init__(self, repository: Repository, clock: Clock = system_clock) -> None:
        self._repository = repository
        self._clock = clock

    def get_invoice(self, organisation_id: int, invoice_id: int) -> Invoice:
        return self._get_invoice(organisation_id, invoice_id)

    def list_invoices(self, organisation_id: int, account_id: int | None = None) -> list[Invoice]:
        return self._repository.list_invoices(organisation_id, account_id=account_id)

    def add_line_item(
        self,
        organisation_id: int,
        invoice_id: int,
        *,
        description: str,
        quantity: Decimal,
        unit_price: Decimal,
        tax_rate: Decimal = Decimal("0"),
    ) -> Invoice:
        invoice = self._get_draft_invoice(organisation_id, invoice_id)
        if not description.strip():
            raise ValidationFailed("description is required")
        _validate_tax_rate(tax_rate)
        item = LineItem(
            id=None,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            tax_rate=tax_rate,
            position=len(invoice.line_items),
        )
        self._repository.add_invoice_line_item(invoice_id, item)
        return self._get_invoice(organisation_id, invoice_id)

    def send(
        self,
        organisation_id: int,
        invoice_id: int,
        *,
        due_date: date_ | None = None,
        payment_terms_days: int | None = None,
    ) -> Invoice:
        invoice = self._get_invoice(organisation_id, invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise InvalidTransition(f"invoice {invoice_id} is not a draft (status={invoice.status.value})")
        if not invoice.line_items:
            raise ValidationFailed(f"invoice {invoice_id} has no line items")
        invoice.number = self._repository.next_invoice_number(organisation_id)
        days = payment_terms_days if payment_terms_days is not None else DEFAULT_INVOICE_DUE_DAYS
        invoice.due_date = due_date or self._clock().date() + timedelta(days=days)
        invoice.status = InvoiceStatus.SENT
        return self._repository.update_invoice(invoice)

    def void(self, organisation_id: int, invoice_id: int) -> Invoice:
        invoice = self._get_invoice(organisation_id, invoice_id)
        if invoice.status == InvoiceStatus.PAID:
            raise InvalidTransition(f"invoice {invoice_id} is already paid, cannot void")
        invoice.status = InvoiceStatus.VOID
        return self._repository.update_invoice(invoice)

    def pay(self, organisation_id: int, invoice_id: int) -> Invoice:
        invoice = self._get_invoice(organisation_id, invoice_id)
        if invoice.status != InvoiceStatus.SENT:
            raise InvalidTransition(
                f"invoice {invoice_id} is not sent (status={invoice.status.value}), cannot mark paid"
            )
        invoice.status = InvoiceStatus.PAID
        return self._repository.update_invoice(invoice)

    def monthly_totals(
        self, organisation_id: int, currency: str, *, months: int = MONTHLY_TOTALS_MONTHS
    ) -> list[MonthlyInvoiceTotals]:
        """Invoice totals for the trailing `months` months (this one
        included), split into paid vs not, for `organisation_id`'s invoices
        in `currency` only - an invoice in a different currency is excluded
        rather than naively summed in (see BusinessProfile.currency).
        Grouped by `issue_date` (when the invoice was created - see
        CLAUDE.md), not `due_date` or `created_at`. Draft invoices (not yet
        issued) and void ones (cancelled) don't count toward either bucket."""
        buckets: dict[str, MonthlyInvoiceTotals] = {}
        order: list[str] = []
        cursor = _month_start(self._clock().date())
        for _ in range(months):
            key = _month_key(cursor)
            order.append(key)
            buckets[key] = MonthlyInvoiceTotals(month=key, paid_total=Decimal("0"), unpaid_total=Decimal("0"))
            cursor = _previous_month(cursor)
        order.reverse()

        for invoice in self._repository.list_invoices(organisation_id):
            if invoice.currency != currency:
                continue
            if invoice.status in (InvoiceStatus.DRAFT, InvoiceStatus.VOID):
                continue
            bucket = buckets.get(_month_key(invoice.issue_date))
            if bucket is None:
                continue
            if invoice.status == InvoiceStatus.PAID:
                bucket.paid_total += invoice.total
            else:
                bucket.unpaid_total += invoice.total

        return [buckets[key] for key in order]

    def _get_invoice(self, organisation_id: int, invoice_id: int) -> Invoice:
        invoice = self._repository.get_invoice(organisation_id, invoice_id)
        if invoice is None:
            raise NotFound(f"invoice {invoice_id} not found")
        return invoice

    def _get_draft_invoice(self, organisation_id: int, invoice_id: int) -> Invoice:
        invoice = self._get_invoice(organisation_id, invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise InvalidTransition(f"invoice {invoice_id} is not editable (status={invoice.status.value})")
        return invoice


class StatsService:
    """`organisation_id`-scoped counters for the home dashboard's stats
    section. A separate service rather than a method on AccountService -
    stats here are expected to grow beyond just accounts (see Stats), so
    this is the one place to add to rather than spreading counts across
    whichever entity's service happens to own the underlying data."""

    def __init__(self, repository: Repository, clock: Clock = system_clock) -> None:
        self._repository = repository
        self._clock = clock

    def get_stats(self, organisation_id: int) -> Stats:
        return Stats(account_count=len(self._repository.list_accounts(organisation_id)))
