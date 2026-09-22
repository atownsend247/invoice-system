import re
from datetime import date as date_
from datetime import timedelta
from decimal import Decimal

from .attachments import AttachmentStore
from .clock import Clock, system_clock
from .errors import Conflict, InvalidTransition, NotFound, ValidationFailed
from .ids import IdGenerator
from .ids import new_id as default_new_id
from .models import (
    Account,
    ActivityEvent,
    ActivityEventType,
    BusinessProfile,
    Domain,
    DomainWithAccount,
    Expense,
    ExpenseAttachment,
    Invoice,
    InvoiceStatus,
    LineItem,
    MonthlyExpenseTotals,
    MonthlyInvoiceTotals,
    Organisation,
    Page,
    Quote,
    QuoteStatus,
    Registrar,
    RegistrarUsage,
    RegistrationInvite,
    Stats,
)
from .repository import Repository

DEFAULT_INVOICE_DUE_DAYS = 30
DEFAULT_PAYMENT_TERMS_DAYS = 30
DEFAULT_QUOTE_VALIDITY_DAYS = 30
DEFAULT_QUOTE_NUMBER_PREFIX = "Q-"
DEFAULT_INVOICE_NUMBER_PREFIX = "INV-"
DEFAULT_EXPENSE_NUMBER_PREFIX = "EXP-"
DEFAULT_NUMBER_DIGITS = 4
DEFAULT_CURRENCY = "GBP"
MONTHLY_TOTALS_MONTHS = 12
DEFAULT_ORGANISATION_NAME = "My Organisation"
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MiB - see ExpenseService.add_attachment
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 200  # see AccountService.list_accounts/QuoteService.list_quotes/InvoiceService.list_invoices
DEFAULT_INVITE_EXPIRY_DAYS = 7  # see RegistrationInviteService.create_invite
# BusinessProfile.accent_color is interpolated directly into a CSS
# declaration by pdf.py's template, not shown as escaped body text like
# every other free-text field on that model - see its docstring - so its
# format is validated here rather than accepted as-is.
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def _validate_pagination(page: int, page_size: int) -> None:
    if page < 1:
        raise ValidationFailed("page must be at least 1")
    if not (1 <= page_size <= MAX_PAGE_SIZE):
        raise ValidationFailed(f"page_size must be between 1 and {MAX_PAGE_SIZE}")


class OrganisationService:
    """Resolves the tenant boundary for a login user - see
    models.py's Organisation docstring and CLAUDE.md's "Four separate
    things" section. Every Account/Quote/Invoice belongs to exactly one
    Organisation; `get_or_create_for_user` is how the API/CLI layers turn
    "which sessionkit user is this" into "which organisation's data can
    they see" before calling into
    AccountService/QuoteService/InvoiceService/StatsService, all of which
    take an `organisation_id` and never resolve one themselves."""

    def __init__(
        self, repository: Repository, clock: Clock = system_clock, new_id: IdGenerator = default_new_id
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id

    def get_or_create_for_user(self, user_id: str, *, default_name: str = DEFAULT_ORGANISATION_NAME) -> str:
        existing = self._repository.get_organisation_id_for_user(user_id)
        if existing is not None:
            return existing
        organisation = self._repository.create_organisation(
            Organisation(id=self._new_id(), name=default_name, created_at=self._clock())
        )
        return self._repository.add_organisation_member(organisation.id, user_id)


class AccountService:
    def __init__(
        self, repository: Repository, clock: Clock = system_clock, new_id: IdGenerator = default_new_id
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id

    def create_account(
        self,
        *,
        organisation_id: str,
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
            id=self._new_id(),
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

    def get_account(self, organisation_id: str, account_id: str) -> Account:
        account = self._repository.get_account(organisation_id, account_id)
        if account is None:
            raise NotFound(f"account {account_id} not found")
        return account

    def list_accounts(
        self,
        organisation_id: str,
        *,
        query: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Page[Account]:
        """`query` matches (case-insensitively) against business/contact
        name, email, phone, or any set address line - the same fields the
        accounts list page's search box checks, now applied server-side
        rather than fetching everything and filtering client-side."""
        _validate_pagination(page, page_size)
        items, total = self._repository.list_accounts(
            organisation_id, query=query, limit=page_size, offset=(page - 1) * page_size
        )
        return Page(items=items, total=total)

    def update_account(
        self,
        organisation_id: str,
        account_id: str,
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


class DomainService:
    """Domains a business tracks - which domain, when it expires, who it's
    registered with (see models.Domain) - organisation-scoped directly
    (own `organisation_id`, resolved the same way `RegistrarService`
    resolves tenant ownership, not through a parent `Account` the way this
    used to work). A domain can exist unlinked (`account_id=None`),
    created independently in the standalone Domains section, and later
    linked to an `Account` from that account's own page via
    `link_domain`/`unlink_domain` - kept deliberately separate from
    `update_domain`, which is a full replace of the domain's own fields
    only (mirroring `AccountService.update_account`) and never touches
    `account_id`, same "dedicated action, not bundled into a general
    update" shape as `InvoiceService.pay`/`void` or
    `BusinessProfileService`'s `set_next_number` actions elsewhere in this
    app. Every mutating method here returns a `DomainWithAccount` (domain
    + the linked account's `business_name`, or `None`), not a bare
    `Domain`, so the caller never needs a second lookup to show which
    account (if any) a domain currently belongs to."""

    def __init__(
        self, repository: Repository, clock: Clock = system_clock, new_id: IdGenerator = default_new_id
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id

    def create_domain(
        self,
        organisation_id: str,
        *,
        domain_name: str,
        expiry_date: date_,
        registrar: str,
        auto_renew: bool = False,
        account_id: str | None = None,
    ) -> DomainWithAccount:
        if account_id is not None:
            self._get_account(organisation_id, account_id)
        if not domain_name.strip():
            raise ValidationFailed("domain_name is required")
        if not registrar.strip():
            raise ValidationFailed("registrar is required")
        now = self._clock()
        domain = Domain(
            id=self._new_id(),
            organisation_id=organisation_id,
            account_id=account_id,
            domain_name=domain_name,
            expiry_date=expiry_date,
            registrar=registrar,
            auto_renew=auto_renew,
            created_at=now,
            updated_at=now,
        )
        created = self._repository.create_domain(domain)
        return self._with_account_name(organisation_id, created)

    def get_domain(self, organisation_id: str, domain_id: str) -> DomainWithAccount:
        return self._with_account_name(organisation_id, self._get_domain(organisation_id, domain_id))

    def list_domains(self, organisation_id: str, *, account_id: str | None = None) -> list[DomainWithAccount]:
        return self._repository.list_domains(organisation_id, account_id=account_id)

    def update_domain(
        self,
        organisation_id: str,
        domain_id: str,
        *,
        domain_name: str,
        expiry_date: date_,
        registrar: str,
        auto_renew: bool,
    ) -> DomainWithAccount:
        existing = self._get_domain(organisation_id, domain_id)
        if not domain_name.strip():
            raise ValidationFailed("domain_name is required")
        if not registrar.strip():
            raise ValidationFailed("registrar is required")
        existing.domain_name = domain_name
        existing.expiry_date = expiry_date
        existing.registrar = registrar
        existing.auto_renew = auto_renew
        existing.updated_at = self._clock()
        updated = self._repository.update_domain(existing)
        return self._with_account_name(organisation_id, updated)

    def link_domain(self, organisation_id: str, domain_id: str, account_id: str) -> DomainWithAccount:
        # Re-linking an already-linked domain to a *different* account is
        # allowed directly, no forced unlink-first step - matches a
        # domain being transferred to a different client.
        existing = self._get_domain(organisation_id, domain_id)
        self._get_account(organisation_id, account_id)
        existing.account_id = account_id
        existing.updated_at = self._clock()
        updated = self._repository.update_domain(existing)
        return self._with_account_name(organisation_id, updated)

    def unlink_domain(self, organisation_id: str, domain_id: str) -> DomainWithAccount:
        existing = self._get_domain(organisation_id, domain_id)
        existing.account_id = None
        existing.updated_at = self._clock()
        updated = self._repository.update_domain(existing)
        return DomainWithAccount(domain=updated, account_name=None)

    def delete_domain(self, organisation_id: str, domain_id: str) -> None:
        self._get_domain(organisation_id, domain_id)  # 404s if missing/wrong organisation
        self._repository.delete_domain(organisation_id, domain_id)

    def _get_account(self, organisation_id: str, account_id: str) -> Account:
        account = self._repository.get_account(organisation_id, account_id)
        if account is None:
            raise NotFound(f"account {account_id} not found")
        return account

    def _get_domain(self, organisation_id: str, domain_id: str) -> Domain:
        domain = self._repository.get_domain(organisation_id, domain_id)
        if domain is None:
            raise NotFound(f"domain {domain_id} not found")
        return domain

    def _with_account_name(self, organisation_id: str, domain: Domain) -> DomainWithAccount:
        account_name = None
        if domain.account_id is not None:
            account = self._repository.get_account(organisation_id, domain.account_id)
            account_name = account.business_name if account is not None else None
        return DomainWithAccount(domain=domain, account_name=account_name)


class RegistrarService:
    """A business's managed list of domain registrars, used to populate
    the Domain form's registrar dropdown (see models.Registrar).
    Organisation-scoped, not account-scoped like DomainService -
    structurally closest to AccountService: its own organisation_id,
    tenant ownership checked directly rather than through a parent.
    Unlike AccountService though, this supports delete - nothing holds a
    foreign key to a Registrar (Domain.registrar stores the chosen name
    as a plain string, not a reference - see models.Domain), so there's
    no database-level cascade to worry about. delete_registrar still
    refuses (Conflict) to delete one that at least one Domain currently
    names - an application-level guard, not a constraint the database
    enforces - see get_registrar_usage/list_registrars_with_usage and
    models.RegistrarUsage."""

    def __init__(
        self, repository: Repository, clock: Clock = system_clock, new_id: IdGenerator = default_new_id
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id

    def create_registrar(self, organisation_id: str, *, name: str, notes: str | None = None) -> Registrar:
        if not name.strip():
            raise ValidationFailed("name is required")
        now = self._clock()
        registrar = Registrar(
            id=self._new_id(),
            organisation_id=organisation_id,
            name=name,
            notes=_blank_to_none(notes),
            created_at=now,
            updated_at=now,
        )
        return self._repository.create_registrar(registrar)

    def get_registrar(self, organisation_id: str, registrar_id: str) -> Registrar:
        return self._get_registrar(organisation_id, registrar_id)

    def list_registrars(self, organisation_id: str) -> list[Registrar]:
        return self._repository.list_registrars(organisation_id)

    def list_registrars_with_usage(self, organisation_id: str) -> list[RegistrarUsage]:
        registrars = self._repository.list_registrars(organisation_id)
        counts = self._repository.count_domains_by_registrar(organisation_id)
        return [self._usage(registrar, counts) for registrar in registrars]

    def get_registrar_usage(self, organisation_id: str, registrar_id: str) -> RegistrarUsage:
        registrar = self._get_registrar(organisation_id, registrar_id)
        counts = self._repository.count_domains_by_registrar(organisation_id)
        return self._usage(registrar, counts)

    @staticmethod
    def _usage(registrar: Registrar, counts: dict[str, tuple[int, int]]) -> RegistrarUsage:
        domain_count, account_count = counts.get(registrar.name, (0, 0))
        return RegistrarUsage(registrar=registrar, domain_count=domain_count, account_count=account_count)

    def update_registrar(
        self, organisation_id: str, registrar_id: str, *, name: str, notes: str | None = None
    ) -> Registrar:
        existing = self._get_registrar(organisation_id, registrar_id)
        if not name.strip():
            raise ValidationFailed("name is required")
        existing.name = name
        existing.notes = _blank_to_none(notes)
        existing.updated_at = self._clock()
        return self._repository.update_registrar(existing)

    def delete_registrar(self, organisation_id: str, registrar_id: str) -> None:
        usage = self.get_registrar_usage(organisation_id, registrar_id)  # 404s if missing/wrong organisation
        if usage.domain_count > 0:
            raise Conflict(
                f"registrar {registrar_id} is still used by {usage.domain_count} domain(s) across "
                f"{usage.account_count} account(s) - remove or reassign them first"
            )
        self._repository.delete_registrar(organisation_id, registrar_id)

    def _get_registrar(self, organisation_id: str, registrar_id: str) -> Registrar:
        registrar = self._repository.get_registrar(organisation_id, registrar_id)
        if registrar is None:
            raise NotFound(f"registrar {registrar_id} not found")
        return registrar


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
    bank details/per-document-type header & footer), one per user - see CLAUDE.md
    for why this is deliberately not an `Account` (that's the client being
    billed) and not part of sessionkit. Deliberately still per-*user*, not
    per-Organisation, even after Organisation was introduced - see
    CLAUDE.md."""

    def __init__(
        self, repository: Repository, clock: Clock = system_clock, new_id: IdGenerator = default_new_id
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id

    def get_profile(self, user_id: str) -> BusinessProfile:
        existing = self._repository.get_business_profile(user_id)
        if existing is not None:
            return existing
        now = self._clock()
        return BusinessProfile(
            id=self._new_id(),
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
            quote_validity_days=DEFAULT_QUOTE_VALIDITY_DAYS,
            currency=DEFAULT_CURRENCY,
            utr=None,
            vat_number=None,
            bank_account_name=None,
            bank_sort_code=None,
            bank_account_number=None,
            quote_document_header=None,
            quote_document_footer=None,
            invoice_document_header=None,
            invoice_document_footer=None,
            expense_document_header=None,
            expense_document_footer=None,
            quote_number_prefix=DEFAULT_QUOTE_NUMBER_PREFIX,
            quote_number_digits=DEFAULT_NUMBER_DIGITS,
            invoice_number_prefix=DEFAULT_INVOICE_NUMBER_PREFIX,
            invoice_number_digits=DEFAULT_NUMBER_DIGITS,
            expense_number_prefix=DEFAULT_EXPENSE_NUMBER_PREFIX,
            expense_number_digits=DEFAULT_NUMBER_DIGITS,
            accent_color=None,
            created_at=now,
            updated_at=now,
        )

    def save_profile(
        self,
        user_id: str,
        *,
        first_name: str,
        last_name: str,
        business_name: str,
        payment_terms_days: int,
        quote_validity_days: int,
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
        quote_document_header: str | None = None,
        quote_document_footer: str | None = None,
        invoice_document_header: str | None = None,
        invoice_document_footer: str | None = None,
        expense_document_header: str | None = None,
        expense_document_footer: str | None = None,
        quote_number_prefix: str,
        quote_number_digits: int,
        invoice_number_prefix: str,
        invoice_number_digits: int,
        expense_number_prefix: str,
        expense_number_digits: int,
        accent_color: str | None = None,
    ) -> BusinessProfile:
        # first_name/last_name/business_name are deliberately NOT validated
        # as non-blank, unlike every other check below - this is a single
        # full-profile PUT covering four tab-separated groups on the
        # settings page (see CLAUDE.md), and these three had no sensible
        # default to fall back to the way payment_terms_days/currency/the
        # number-prefix fields do. Requiring them non-blank meant a user
        # filling in just one tab (e.g. Document) before ever touching
        # User/Business couldn't save at all - blank is accepted and
        # stored as "" (not normalised to None - these stay a plain `str`,
        # not `str | None`, since nothing downstream needs to distinguish
        # "never set" from "set to blank": pdf.py's business_profile_lines()
        # already checks `if not profile.business_name.strip()`, treating
        # both the same way).
        if payment_terms_days <= 0:
            raise ValidationFailed("payment_terms_days must be a positive number of days")
        if quote_validity_days <= 0:
            raise ValidationFailed("quote_validity_days must be a positive number of days")
        if quote_number_digits < 1:
            raise ValidationFailed("quote_number_digits must be at least 1")
        if invoice_number_digits < 1:
            raise ValidationFailed("invoice_number_digits must be at least 1")
        if expense_number_digits < 1:
            raise ValidationFailed("expense_number_digits must be at least 1")
        if not currency.strip():
            raise ValidationFailed("currency is required")
        accent_color = _blank_to_none(accent_color)
        if accent_color is not None and not _HEX_COLOR_PATTERN.match(accent_color):
            raise ValidationFailed("accent_color must be a #RRGGBB hex colour")

        existing = self._repository.get_business_profile(user_id)
        created_at = existing.created_at if existing is not None else self._clock()
        profile = BusinessProfile(
            id=existing.id if existing is not None else self._new_id(),
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
            quote_validity_days=quote_validity_days,
            currency=currency.strip().upper(),
            utr=_blank_to_none(utr),
            vat_number=_blank_to_none(vat_number),
            bank_account_name=_blank_to_none(bank_account_name),
            bank_sort_code=_blank_to_none(bank_sort_code),
            bank_account_number=_blank_to_none(bank_account_number),
            quote_document_header=_blank_to_none(quote_document_header),
            quote_document_footer=_blank_to_none(quote_document_footer),
            invoice_document_header=_blank_to_none(invoice_document_header),
            invoice_document_footer=_blank_to_none(invoice_document_footer),
            expense_document_header=_blank_to_none(expense_document_header),
            expense_document_footer=_blank_to_none(expense_document_footer),
            quote_number_prefix=quote_number_prefix,
            quote_number_digits=quote_number_digits,
            invoice_number_prefix=invoice_number_prefix,
            invoice_number_digits=invoice_number_digits,
            expense_number_prefix=expense_number_prefix,
            expense_number_digits=expense_number_digits,
            accent_color=accent_color,
            created_at=created_at,
            updated_at=self._clock(),
        )
        return self._repository.upsert_business_profile(profile)


class QuoteService:
    def __init__(
        self, repository: Repository, clock: Clock = system_clock, new_id: IdGenerator = default_new_id
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id

    def create_quote(
        self,
        *,
        organisation_id: str,
        account_id: str,
        currency: str = "USD",
        issue_date: date_ | None = None,
        quote_validity_days: int | None = None,
    ) -> Quote:
        if self._repository.get_account(organisation_id, account_id) is None:
            raise NotFound(f"account {account_id} not found")
        resolved_issue_date = issue_date or self._clock().date()
        days = quote_validity_days if quote_validity_days is not None else DEFAULT_QUOTE_VALIDITY_DAYS
        quote = Quote(
            id=self._new_id(),
            organisation_id=organisation_id,
            account_id=account_id,
            number=None,
            status=QuoteStatus.DRAFT,
            currency=currency,
            issue_date=resolved_issue_date,
            expiry_date=resolved_issue_date + timedelta(days=days),
            created_at=self._clock(),
        )
        quote = self._repository.create_quote(quote)
        self._record_event(quote.id, from_status=None, to_status=quote.status)
        return self._get_quote(organisation_id, quote.id)

    def get_quote(self, organisation_id: str, quote_id: str) -> Quote:
        return self._get_quote(organisation_id, quote_id)

    def list_quotes(
        self,
        organisation_id: str,
        *,
        account_id: str | None = None,
        account_name: str | None = None,
        status: QuoteStatus | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Page[Quote]:
        """`account_name` matches (case-insensitively) against the linked
        account's business_name - the quotes list page's account filter,
        applied server-side."""
        _validate_pagination(page, page_size)
        items, total = self._repository.list_quotes(
            organisation_id,
            account_id=account_id,
            account_name=account_name,
            status=status,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return Page(items=items, total=total)

    def add_line_item(
        self,
        organisation_id: str,
        quote_id: str,
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
            id=self._new_id(),
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            tax_rate=tax_rate,
            position=len(quote.line_items),
        )
        self._repository.add_quote_line_item(quote_id, item)
        return self._get_quote(organisation_id, quote_id)

    def send(
        self,
        organisation_id: str,
        quote_id: str,
        *,
        number_prefix: str | None = None,
        number_digits: int | None = None,
    ) -> Quote:
        quote = self._get_quote(organisation_id, quote_id)
        if quote.status != QuoteStatus.DRAFT:
            raise InvalidTransition(f"quote {quote_id} is not a draft (status={quote.status.value})")
        if not quote.line_items:
            raise ValidationFailed(f"quote {quote_id} has no line items")
        prefix = number_prefix if number_prefix is not None else DEFAULT_QUOTE_NUMBER_PREFIX
        digits = number_digits if number_digits is not None else DEFAULT_NUMBER_DIGITS
        quote.number = self._repository.next_quote_number(organisation_id, prefix, digits)
        from_status = quote.status
        quote.status = QuoteStatus.SENT
        self._repository.update_quote(quote)
        self._record_event(quote.id, from_status=from_status, to_status=quote.status)
        return self._get_quote(organisation_id, quote_id)

    def set_next_number(self, organisation_id: str, next_number: int) -> None:
        if next_number < 1:
            raise ValidationFailed("next_number must be at least 1")
        self._repository.set_next_quote_number(organisation_id, next_number)

    def mark_accepted(self, organisation_id: str, quote_id: str) -> Quote:
        return self._transition(
            organisation_id, quote_id, from_status=QuoteStatus.SENT, to_status=QuoteStatus.ACCEPTED
        )

    def mark_rejected(self, organisation_id: str, quote_id: str) -> Quote:
        return self._transition(
            organisation_id, quote_id, from_status=QuoteStatus.SENT, to_status=QuoteStatus.REJECTED
        )

    def mark_expired(self, organisation_id: str, quote_id: str) -> Quote:
        return self._transition(
            organisation_id, quote_id, from_status=QuoteStatus.SENT, to_status=QuoteStatus.EXPIRED
        )

    def convert_to_invoice(
        self, organisation_id: str, quote_id: str, *, issue_date: date_ | None = None
    ) -> Invoice:
        quote = self._get_quote(organisation_id, quote_id)
        if quote.status not in (QuoteStatus.SENT, QuoteStatus.ACCEPTED):
            raise InvalidTransition(f"quote {quote_id} cannot be converted from status {quote.status.value}")
        invoice = Invoice(
            id=self._new_id(),
            organisation_id=organisation_id,
            account_id=quote.account_id,
            quote_id=quote.id,
            number=None,
            status=InvoiceStatus.DRAFT,
            currency=quote.currency,
            issue_date=issue_date or self._clock().date(),
            due_date=None,
            created_at=self._clock(),
        )
        invoice = self._repository.create_invoice(invoice)
        for item in quote.line_items:
            self._repository.add_invoice_line_item(
                invoice.id,
                LineItem(
                    id=self._new_id(),
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    tax_rate=item.tax_rate,
                    position=item.position,
                ),
            )
        self._repository.add_invoice_event(
            invoice.id,
            ActivityEvent(
                id=self._new_id(),
                event_type=ActivityEventType.CREATED,
                from_status=None,
                to_status=invoice.status.value,
                occurred_at=self._clock(),
            ),
        )
        from_status = quote.status
        quote.status = QuoteStatus.CONVERTED
        self._repository.update_quote(quote)
        self._record_event(quote.id, from_status=from_status, to_status=quote.status)
        return self._repository.get_invoice(organisation_id, invoice.id)

    def _transition(
        self, organisation_id: str, quote_id: str, *, from_status: QuoteStatus, to_status: QuoteStatus
    ) -> Quote:
        quote = self._get_quote(organisation_id, quote_id)
        if quote.status != from_status:
            raise InvalidTransition(
                f"quote {quote_id} must be {from_status.value} to become {to_status.value} "
                f"(status={quote.status.value})"
            )
        quote.status = to_status
        self._repository.update_quote(quote)
        self._record_event(quote.id, from_status=from_status, to_status=to_status)
        return self._get_quote(organisation_id, quote_id)

    def _record_event(
        self, quote_id: str, *, from_status: QuoteStatus | None, to_status: QuoteStatus
    ) -> None:
        self._repository.add_quote_event(
            quote_id,
            ActivityEvent(
                id=self._new_id(),
                event_type=ActivityEventType.CREATED
                if from_status is None
                else ActivityEventType.STATUS_CHANGED,
                from_status=from_status.value if from_status else None,
                to_status=to_status.value,
                occurred_at=self._clock(),
            ),
        )

    def _get_quote(self, organisation_id: str, quote_id: str) -> Quote:
        quote = self._repository.get_quote(organisation_id, quote_id)
        if quote is None:
            raise NotFound(f"quote {quote_id} not found")
        return quote

    def _get_draft_quote(self, organisation_id: str, quote_id: str) -> Quote:
        quote = self._get_quote(organisation_id, quote_id)
        if quote.status != QuoteStatus.DRAFT:
            raise InvalidTransition(f"quote {quote_id} is not editable (status={quote.status.value})")
        return quote


class InvoiceService:
    def __init__(
        self, repository: Repository, clock: Clock = system_clock, new_id: IdGenerator = default_new_id
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id

    def get_invoice(self, organisation_id: str, invoice_id: str) -> Invoice:
        return self._get_invoice(organisation_id, invoice_id)

    def list_invoices(
        self,
        organisation_id: str,
        *,
        account_id: str | None = None,
        account_name: str | None = None,
        status: InvoiceStatus | None = None,
        quote_id: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Page[Invoice]:
        """`account_name` matches (case-insensitively) against the linked
        account's business_name - the invoices list page's account filter,
        applied server-side. `status` is whatever's actually stored
        (draft/sent/paid/void) - `overdue` is presentation-only and never
        written to Invoice.status (see monthly_totals below), so filtering
        by it would only ever match zero rows; nothing stops a caller
        passing it, it just isn't useful. `quote_id` matches at most one
        invoice - a quote converts to at most one invoice
        (convert_to_invoice can only run once per quote) - used to find
        the invoice a given quote became, without storing a redundant
        reverse reference back on Quote (Invoice.quote_id already exists)."""
        _validate_pagination(page, page_size)
        items, total = self._repository.list_invoices(
            organisation_id,
            account_id=account_id,
            account_name=account_name,
            status=status,
            quote_id=quote_id,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return Page(items=items, total=total)

    def add_line_item(
        self,
        organisation_id: str,
        invoice_id: str,
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
            id=self._new_id(),
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
        organisation_id: str,
        invoice_id: str,
        *,
        due_date: date_ | None = None,
        payment_terms_days: int | None = None,
        number_prefix: str | None = None,
        number_digits: int | None = None,
    ) -> Invoice:
        invoice = self._get_invoice(organisation_id, invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise InvalidTransition(f"invoice {invoice_id} is not a draft (status={invoice.status.value})")
        if not invoice.line_items:
            raise ValidationFailed(f"invoice {invoice_id} has no line items")
        prefix = number_prefix if number_prefix is not None else DEFAULT_INVOICE_NUMBER_PREFIX
        digits = number_digits if number_digits is not None else DEFAULT_NUMBER_DIGITS
        invoice.number = self._repository.next_invoice_number(organisation_id, prefix, digits)
        days = payment_terms_days if payment_terms_days is not None else DEFAULT_INVOICE_DUE_DAYS
        invoice.due_date = due_date or invoice.issue_date + timedelta(days=days)
        from_status = invoice.status
        invoice.status = InvoiceStatus.SENT
        self._repository.update_invoice(invoice)
        self._record_event(invoice.id, from_status=from_status, to_status=invoice.status)
        return self._get_invoice(organisation_id, invoice_id)

    def set_next_number(self, organisation_id: str, next_number: int) -> None:
        if next_number < 1:
            raise ValidationFailed("next_number must be at least 1")
        self._repository.set_next_invoice_number(organisation_id, next_number)

    def void(self, organisation_id: str, invoice_id: str) -> Invoice:
        invoice = self._get_invoice(organisation_id, invoice_id)
        if invoice.status == InvoiceStatus.PAID:
            raise InvalidTransition(f"invoice {invoice_id} is already paid, cannot void")
        from_status = invoice.status
        invoice.status = InvoiceStatus.VOID
        self._repository.update_invoice(invoice)
        self._record_event(invoice.id, from_status=from_status, to_status=invoice.status)
        return self._get_invoice(organisation_id, invoice_id)

    def pay(self, organisation_id: str, invoice_id: str) -> Invoice:
        invoice = self._get_invoice(organisation_id, invoice_id)
        if invoice.status != InvoiceStatus.SENT:
            raise InvalidTransition(
                f"invoice {invoice_id} is not sent (status={invoice.status.value}), cannot mark paid"
            )
        from_status = invoice.status
        invoice.status = InvoiceStatus.PAID
        self._repository.update_invoice(invoice)
        self._record_event(invoice.id, from_status=from_status, to_status=invoice.status)
        return self._get_invoice(organisation_id, invoice_id)

    def _record_event(
        self, invoice_id: str, *, from_status: InvoiceStatus | None, to_status: InvoiceStatus
    ) -> None:
        self._repository.add_invoice_event(
            invoice_id,
            ActivityEvent(
                id=self._new_id(),
                event_type=ActivityEventType.CREATED
                if from_status is None
                else ActivityEventType.STATUS_CHANGED,
                from_status=from_status.value if from_status else None,
                to_status=to_status.value,
                occurred_at=self._clock(),
            ),
        )

    def monthly_totals(
        self, organisation_id: str, currency: str, *, months: int = MONTHLY_TOTALS_MONTHS
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

        invoices, _ = self._repository.list_invoices(organisation_id)
        for invoice in invoices:
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

    def _get_invoice(self, organisation_id: str, invoice_id: str) -> Invoice:
        invoice = self._repository.get_invoice(organisation_id, invoice_id)
        if invoice is None:
            raise NotFound(f"invoice {invoice_id} not found")
        return invoice

    def _get_draft_invoice(self, organisation_id: str, invoice_id: str) -> Invoice:
        invoice = self._get_invoice(organisation_id, invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise InvalidTransition(f"invoice {invoice_id} is not editable (status={invoice.status.value})")
        return invoice


class ExpenseService:
    """Costs incurred against an Account - see models.Expense. Unlike
    QuoteService/InvoiceService there's no draft/sent lifecycle: an expense
    is a record of money already spent, not a document issued to anyone,
    so `create_expense` assigns its EXP-0001 number immediately rather than
    deferring that to a later `send()` the way Quote/Invoice do, and
    `add_line_item` isn't gated behind a status check the way
    QuoteService.add_line_item requires `draft`.

    `attachments` is an injected `AttachmentStore` (see attachments.py) -
    the only ambient dependency here that isn't a plain function like
    `clock`/`new_id`, since it needs a base directory to write to; there's
    no sensible parameterless default to fall back to, so unlike those two
    it's a required constructor argument, not an optional one."""

    def __init__(
        self,
        repository: Repository,
        clock: Clock = system_clock,
        new_id: IdGenerator = default_new_id,
        *,
        attachments: AttachmentStore,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id
        self._attachments = attachments

    def create_expense(
        self,
        *,
        organisation_id: str,
        account_id: str,
        currency: str = "USD",
        expense_date: date_ | None = None,
        number_prefix: str | None = None,
        number_digits: int | None = None,
    ) -> Expense:
        if self._repository.get_account(organisation_id, account_id) is None:
            raise NotFound(f"account {account_id} not found")
        prefix = number_prefix if number_prefix is not None else DEFAULT_EXPENSE_NUMBER_PREFIX
        digits = number_digits if number_digits is not None else DEFAULT_NUMBER_DIGITS
        expense = Expense(
            id=self._new_id(),
            organisation_id=organisation_id,
            account_id=account_id,
            number=self._repository.next_expense_number(organisation_id, prefix, digits),
            currency=currency,
            issue_date=self._clock().date(),
            expense_date=expense_date if expense_date is not None else self._clock().date(),
            created_at=self._clock(),
        )
        return self._repository.create_expense(expense)

    def set_next_number(self, organisation_id: str, next_number: int) -> None:
        if next_number < 1:
            raise ValidationFailed("next_number must be at least 1")
        self._repository.set_next_expense_number(organisation_id, next_number)

    def get_expense(self, organisation_id: str, expense_id: str) -> Expense:
        return self._get_expense(organisation_id, expense_id)

    def list_expenses(self, organisation_id: str, account_id: str | None = None) -> list[Expense]:
        return self._repository.list_expenses(organisation_id, account_id=account_id)

    def update_expense_date(self, organisation_id: str, expense_id: str, expense_date: date_) -> Expense:
        expense = self._get_expense(organisation_id, expense_id)
        expense.expense_date = expense_date
        return self._repository.update_expense_date(expense)

    def add_line_item(
        self,
        organisation_id: str,
        expense_id: str,
        *,
        description: str,
        quantity: Decimal,
        unit_price: Decimal,
        tax_rate: Decimal = Decimal("0"),
    ) -> Expense:
        expense = self._get_expense(organisation_id, expense_id)
        if not description.strip():
            raise ValidationFailed("description is required")
        _validate_tax_rate(tax_rate)
        item = LineItem(
            id=self._new_id(),
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            tax_rate=tax_rate,
            position=len(expense.line_items),
        )
        self._repository.add_expense_line_item(expense_id, item)
        return self._get_expense(organisation_id, expense_id)

    def update_line_item(
        self,
        organisation_id: str,
        expense_id: str,
        item_id: str,
        *,
        description: str,
        quantity: Decimal,
        unit_price: Decimal,
        tax_rate: Decimal = Decimal("0"),
    ) -> Expense:
        expense = self._get_expense(organisation_id, expense_id)
        existing = self._get_line_item(expense, item_id)
        if not description.strip():
            raise ValidationFailed("description is required")
        _validate_tax_rate(tax_rate)
        item = LineItem(
            id=existing.id,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            tax_rate=tax_rate,
            position=existing.position,
        )
        self._repository.update_expense_line_item(expense_id, item)
        return self._get_expense(organisation_id, expense_id)

    def delete_line_item(self, organisation_id: str, expense_id: str, item_id: str) -> Expense:
        expense = self._get_expense(organisation_id, expense_id)
        self._get_line_item(expense, item_id)
        self._repository.delete_expense_line_item(expense_id, item_id)
        return self._get_expense(organisation_id, expense_id)

    @staticmethod
    def _get_line_item(expense: Expense, item_id: str) -> LineItem:
        for item in expense.line_items:
            if item.id == item_id:
                return item
        raise NotFound(f"line item {item_id} not found")

    def monthly_totals(
        self, organisation_id: str, currency: str, *, months: int = MONTHLY_TOTALS_MONTHS
    ) -> list[MonthlyExpenseTotals]:
        """Expense totals for the trailing `months` months (this one
        included), for `organisation_id`'s expenses in `currency` only -
        same currency-filtering convention as InvoiceService.monthly_totals,
        an expense in a different currency is excluded rather than naively
        summed in. Grouped by `expense_date` - when the money was actually
        spent, not `issue_date` (when the record was created) - so
        backdating an entry (e.g. logging a receipt from last week) counts
        it against the month it actually happened in, not the month it was
        typed in. No paid/unpaid split - an Expense has no status (see
        models.Expense)."""
        buckets: dict[str, MonthlyExpenseTotals] = {}
        order: list[str] = []
        cursor = _month_start(self._clock().date())
        for _ in range(months):
            key = _month_key(cursor)
            order.append(key)
            buckets[key] = MonthlyExpenseTotals(month=key, total=Decimal("0"))
            cursor = _previous_month(cursor)
        order.reverse()

        for expense in self._repository.list_expenses(organisation_id):
            if expense.currency != currency:
                continue
            bucket = buckets.get(_month_key(expense.expense_date))
            if bucket is None:
                continue
            bucket.total += expense.total

        return [buckets[key] for key in order]

    def add_attachment(
        self,
        organisation_id: str,
        expense_id: str,
        *,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> ExpenseAttachment:
        """Uploads a supplementary PDF (e.g. a scanned receipt) against an
        expense - addable at any time, same no-lifecycle reasoning as
        add_line_item above. The file is saved to disk *before* the
        metadata row is inserted: if the write fails, nothing references
        it; if it's the insert that fails afterwards, the orphaned file on
        disk is harmless (nothing else generates that id), whereas the
        reverse order could leave a DB row pointing at a file that was
        never actually written."""
        self._get_expense(organisation_id, expense_id)  # 404s if missing/wrong organisation
        if not filename.strip():
            raise ValidationFailed("filename is required")
        if content_type != "application/pdf" and not filename.lower().endswith(".pdf"):
            raise ValidationFailed("only PDF attachments are supported")
        if not data:
            raise ValidationFailed("attachment is empty")
        if len(data) > MAX_ATTACHMENT_SIZE:
            raise ValidationFailed(f"attachment exceeds the {MAX_ATTACHMENT_SIZE // (1024 * 1024)}MB limit")

        attachment = ExpenseAttachment(
            id=self._new_id(),
            expense_id=expense_id,
            filename=filename,
            content_type=content_type,
            size=len(data),
            created_at=self._clock(),
        )
        self._attachments.save(attachment.id, data)
        return self._repository.create_expense_attachment(attachment)

    def get_attachment_bytes(
        self, organisation_id: str, expense_id: str, attachment_id: str
    ) -> tuple[ExpenseAttachment, bytes]:
        self._get_expense(organisation_id, expense_id)  # 404s if missing/wrong organisation
        attachment = self._get_attachment(expense_id, attachment_id)
        return attachment, self._attachments.read(attachment.id)

    def delete_attachment(self, organisation_id: str, expense_id: str, attachment_id: str) -> None:
        self._get_expense(organisation_id, expense_id)  # 404s if missing/wrong organisation
        attachment = self._get_attachment(expense_id, attachment_id)
        # DB row first, then the file - the reverse order could leave a
        # row pointing at a file that no longer exists if the delete were
        # interrupted between the two steps; an orphaned file with no
        # referencing row is merely wasted disk space, never a broken
        # reference (same reasoning as add_attachment's ordering above).
        self._repository.delete_expense_attachment(expense_id, attachment_id)
        self._attachments.delete(attachment.id)

    def _get_attachment(self, expense_id: str, attachment_id: str) -> ExpenseAttachment:
        attachment = self._repository.get_expense_attachment(expense_id, attachment_id)
        if attachment is None:
            raise NotFound(f"attachment {attachment_id} not found")
        return attachment

    def _get_expense(self, organisation_id: str, expense_id: str) -> Expense:
        expense = self._repository.get_expense(organisation_id, expense_id)
        if expense is None:
            raise NotFound(f"expense {expense_id} not found")
        return expense


class StatsService:
    """`organisation_id`-scoped counters for the home dashboard's stats
    section. A separate service rather than a method on AccountService -
    stats here are expected to grow beyond just accounts (see Stats), so
    this is the one place to add to rather than spreading counts across
    whichever entity's service happens to own the underlying data."""

    def __init__(self, repository: Repository, clock: Clock = system_clock) -> None:
        self._repository = repository
        self._clock = clock

    def get_stats(self, organisation_id: str, currency: str) -> Stats:
        """`total_paid` is filtered to `currency` only, same convention as
        InvoiceService.monthly_totals - an invoice in a different currency
        is excluded rather than naively summed in. This service doesn't
        know whose profile `currency` came from, same as monthly_totals."""
        accounts, _ = self._repository.list_accounts(organisation_id)
        quotes, _ = self._repository.list_quotes(organisation_id)
        invoices, _ = self._repository.list_invoices(organisation_id)

        quotes_sent_count = sum(1 for q in quotes if q.status != QuoteStatus.DRAFT)
        quotes_converted_count = sum(1 for q in quotes if q.status == QuoteStatus.CONVERTED)
        total_paid = sum(
            (i.total for i in invoices if i.status == InvoiceStatus.PAID and i.currency == currency),
            Decimal("0"),
        )

        return Stats(
            account_count=len(accounts),
            quote_count=len(quotes),
            invoice_count=len(invoices),
            quotes_sent_count=quotes_sent_count,
            quotes_converted_count=quotes_converted_count,
            total_paid=total_paid,
        )


class RegistrationInviteService:
    """Single-use, time-limited tokens gating the public `/register` page -
    see models.RegistrationInvite. Deliberately never imports or knows
    about `sessionkit` (see CLAUDE.md's architecture rules) - it only
    manages the invite row itself; the one place that actually creates a
    login (`sessionkit.AuthService.create_user`) is `api/auth.py`'s `POST
    /auth/register` route handler, which calls `consume_invite` here
    first."""

    def __init__(
        self, repository: Repository, clock: Clock = system_clock, new_id: IdGenerator = default_new_id
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._new_id = new_id

    def create_invite(self, *, expires_in_days: int = DEFAULT_INVITE_EXPIRY_DAYS) -> RegistrationInvite:
        now = self._clock()
        invite = RegistrationInvite(
            token=self._new_id(),
            created_at=now,
            expires_at=now + timedelta(days=expires_in_days),
            used_at=None,
        )
        return self._repository.create_registration_invite(invite)

    def check_invite(self, token: str) -> None:
        """Raises NotFound if `token` is unknown, expired, or already used
        - the same error either way, deliberately (see
        models.RegistrationInvite's docstring on why)."""
        invite = self._repository.get_registration_invite(token)
        if invite is None or invite.used_at is not None or invite.expires_at < self._clock():
            raise NotFound("invite is invalid or has expired")

    def consume_invite(self, token: str) -> None:
        """Claims `token` for use, atomically - see
        SqliteRepository.consume_registration_invite. Called before the
        sessionkit user is actually created (`api/auth.py`'s `POST
        /auth/register`), not after: if that later step fails (e.g. a
        duplicate email), the invite is burned but no two callers can ever
        both succeed with the same one-time token."""
        self.check_invite(token)
        if not self._repository.consume_registration_invite(token, used_at=self._clock()):
            raise NotFound("invite is invalid or has expired")
