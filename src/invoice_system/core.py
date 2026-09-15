from datetime import date as date_
from datetime import timedelta
from decimal import Decimal

from .clock import Clock, system_clock
from .errors import InvalidTransition, NotFound, ValidationFailed
from .models import Account, BusinessProfile, Invoice, InvoiceStatus, LineItem, Quote, QuoteStatus
from .repository import Repository

DEFAULT_INVOICE_DUE_DAYS = 30
DEFAULT_PAYMENT_TERMS_DAYS = 30


class AccountService:
    def __init__(self, repository: Repository, clock: Clock = system_clock) -> None:
        self._repository = repository
        self._clock = clock

    def create_account(
        self,
        *,
        business_name: str,
        email: str,
        address: str,
        contact_name: str | None = None,
        phone: str | None = None,
    ) -> Account:
        if not business_name.strip():
            raise ValidationFailed("business_name is required")
        if not email.strip():
            raise ValidationFailed("email is required")
        if not address.strip():
            raise ValidationFailed("address is required")
        account = Account(
            id=None,
            business_name=business_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            address=address,
            created_at=self._clock(),
        )
        return self._repository.create_account(account)

    def get_account(self, account_id: int) -> Account:
        account = self._repository.get_account(account_id)
        if account is None:
            raise NotFound(f"account {account_id} not found")
        return account

    def list_accounts(self) -> list[Account]:
        return self._repository.list_accounts()


class BusinessProfileService:
    """The logged-in user's own business details (name/address/payment terms/
    UTR/VAT), one per user - see CLAUDE.md for why this is deliberately not
    an `Account` (that's the client being billed) and not part of sessionkit."""

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
            business_address=None,
            payment_terms_days=DEFAULT_PAYMENT_TERMS_DAYS,
            utr=None,
            vat_number=None,
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
        business_address: str | None = None,
        utr: str | None = None,
        vat_number: str | None = None,
    ) -> BusinessProfile:
        if not first_name.strip():
            raise ValidationFailed("first_name is required")
        if not last_name.strip():
            raise ValidationFailed("last_name is required")
        if not business_name.strip():
            raise ValidationFailed("business_name is required")
        if payment_terms_days <= 0:
            raise ValidationFailed("payment_terms_days must be a positive number of days")

        existing = self._repository.get_business_profile(user_id)
        created_at = existing.created_at if existing is not None else self._clock()
        profile = BusinessProfile(
            id=existing.id if existing is not None else None,
            user_id=user_id,
            title=title.strip() if title and title.strip() else None,
            first_name=first_name,
            last_name=last_name,
            business_name=business_name,
            business_address=business_address.strip()
            if business_address and business_address.strip()
            else None,
            payment_terms_days=payment_terms_days,
            utr=utr.strip() if utr and utr.strip() else None,
            vat_number=vat_number.strip() if vat_number and vat_number.strip() else None,
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
        account_id: int,
        currency: str = "USD",
        expiry_date: date_ | None = None,
    ) -> Quote:
        if self._repository.get_account(account_id) is None:
            raise NotFound(f"account {account_id} not found")
        quote = Quote(
            id=None,
            account_id=account_id,
            number=None,
            status=QuoteStatus.DRAFT,
            currency=currency,
            issue_date=self._clock().date(),
            expiry_date=expiry_date,
            created_at=self._clock(),
        )
        return self._repository.create_quote(quote)

    def get_quote(self, quote_id: int) -> Quote:
        return self._get_quote(quote_id)

    def list_quotes(self, account_id: int | None = None) -> list[Quote]:
        return self._repository.list_quotes(account_id=account_id)

    def add_line_item(
        self, quote_id: int, *, description: str, quantity: Decimal, unit_price: Decimal
    ) -> Quote:
        quote = self._get_draft_quote(quote_id)
        if not description.strip():
            raise ValidationFailed("description is required")
        item = LineItem(
            id=None,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            position=len(quote.line_items),
        )
        self._repository.add_quote_line_item(quote_id, item)
        return self._get_quote(quote_id)

    def send(self, quote_id: int) -> Quote:
        quote = self._get_quote(quote_id)
        if quote.status != QuoteStatus.DRAFT:
            raise InvalidTransition(f"quote {quote_id} is not a draft (status={quote.status.value})")
        if not quote.line_items:
            raise ValidationFailed(f"quote {quote_id} has no line items")
        quote.number = self._repository.next_quote_number()
        quote.status = QuoteStatus.SENT
        return self._repository.update_quote(quote)

    def mark_accepted(self, quote_id: int) -> Quote:
        return self._transition(quote_id, from_status=QuoteStatus.SENT, to_status=QuoteStatus.ACCEPTED)

    def mark_rejected(self, quote_id: int) -> Quote:
        return self._transition(quote_id, from_status=QuoteStatus.SENT, to_status=QuoteStatus.REJECTED)

    def mark_expired(self, quote_id: int) -> Quote:
        return self._transition(quote_id, from_status=QuoteStatus.SENT, to_status=QuoteStatus.EXPIRED)

    def convert_to_invoice(self, quote_id: int) -> Invoice:
        quote = self._get_quote(quote_id)
        if quote.status not in (QuoteStatus.SENT, QuoteStatus.ACCEPTED):
            raise InvalidTransition(f"quote {quote_id} cannot be converted from status {quote.status.value}")
        invoice = Invoice(
            id=None,
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
                    position=item.position,
                ),
            )
        quote.status = QuoteStatus.CONVERTED
        self._repository.update_quote(quote)
        return self._repository.get_invoice(invoice.id)

    def _transition(self, quote_id: int, *, from_status: QuoteStatus, to_status: QuoteStatus) -> Quote:
        quote = self._get_quote(quote_id)
        if quote.status != from_status:
            raise InvalidTransition(
                f"quote {quote_id} must be {from_status.value} to become {to_status.value} "
                f"(status={quote.status.value})"
            )
        quote.status = to_status
        return self._repository.update_quote(quote)

    def _get_quote(self, quote_id: int) -> Quote:
        quote = self._repository.get_quote(quote_id)
        if quote is None:
            raise NotFound(f"quote {quote_id} not found")
        return quote

    def _get_draft_quote(self, quote_id: int) -> Quote:
        quote = self._get_quote(quote_id)
        if quote.status != QuoteStatus.DRAFT:
            raise InvalidTransition(f"quote {quote_id} is not editable (status={quote.status.value})")
        return quote


class InvoiceService:
    def __init__(self, repository: Repository, clock: Clock = system_clock) -> None:
        self._repository = repository
        self._clock = clock

    def get_invoice(self, invoice_id: int) -> Invoice:
        return self._get_invoice(invoice_id)

    def list_invoices(self, account_id: int | None = None) -> list[Invoice]:
        return self._repository.list_invoices(account_id=account_id)

    def add_line_item(
        self, invoice_id: int, *, description: str, quantity: Decimal, unit_price: Decimal
    ) -> Invoice:
        invoice = self._get_draft_invoice(invoice_id)
        if not description.strip():
            raise ValidationFailed("description is required")
        item = LineItem(
            id=None,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            position=len(invoice.line_items),
        )
        self._repository.add_invoice_line_item(invoice_id, item)
        return self._get_invoice(invoice_id)

    def send(
        self,
        invoice_id: int,
        *,
        due_date: date_ | None = None,
        payment_terms_days: int | None = None,
    ) -> Invoice:
        invoice = self._get_invoice(invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise InvalidTransition(f"invoice {invoice_id} is not a draft (status={invoice.status.value})")
        if not invoice.line_items:
            raise ValidationFailed(f"invoice {invoice_id} has no line items")
        invoice.number = self._repository.next_invoice_number()
        days = payment_terms_days if payment_terms_days is not None else DEFAULT_INVOICE_DUE_DAYS
        invoice.due_date = due_date or self._clock().date() + timedelta(days=days)
        invoice.status = InvoiceStatus.SENT
        return self._repository.update_invoice(invoice)

    def void(self, invoice_id: int) -> Invoice:
        invoice = self._get_invoice(invoice_id)
        if invoice.status == InvoiceStatus.PAID:
            raise InvalidTransition(f"invoice {invoice_id} is already paid, cannot void")
        invoice.status = InvoiceStatus.VOID
        return self._repository.update_invoice(invoice)

    def _get_invoice(self, invoice_id: int) -> Invoice:
        invoice = self._repository.get_invoice(invoice_id)
        if invoice is None:
            raise NotFound(f"invoice {invoice_id} not found")
        return invoice

    def _get_draft_invoice(self, invoice_id: int) -> Invoice:
        invoice = self._get_invoice(invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise InvalidTransition(f"invoice {invoice_id} is not editable (status={invoice.status.value})")
        return invoice
