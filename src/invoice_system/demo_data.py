"""Demo data: a 12-month spread of accounts, quotes, and invoices in a
mix of statuses, plus a demo login user and business profile - seeded by
`invoice-system-cli init-db` unless `--no-demo` is passed (see CLAUDE.md).

**Keep this in sync with the rest of the app.** When a feature changes what
an Account/Quote/Invoice/BusinessProfile can look like (a new field, a new
status, a new line-item property), update the data here so the demo still
shows it off - a stale demo dataset that only exercises last year's feature
set is worse than none, because it quietly stops being a smoke test for
anything new. Volume matters too, not just variety: accounts/quotes/
invoices are each seeded past 20 rows (`_filler_accounts`/
`_FILLER_INVOICE_TYPES` below, on top of the five named accounts and
fourteen curated quote/invoice scenarios) specifically so the demo instance
actually shows a second page on `AccountsPage.tsx`/`QuotesPage.tsx`/
`InvoicesPage.tsx` (`PAGE_SIZE=20`) rather than pagination only ever being
exercised by e2e tests that create their own bulk data.

Idempotent: re-running `init-db --demo` against a database that already has
the demo user does nothing further (checked via sessionkit's DuplicateUser),
so it's safe to run on every fresh `init-db` without piling up duplicates.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate
from sessionkit import DuplicateUser

from .auth import Auth
from .core import (
    AccountService,
    BusinessProfileService,
    DomainService,
    ExpenseService,
    InvoiceService,
    OrganisationService,
    QuoteService,
)
from .factory import Application

DEMO_EMAIL = "demo@example.test"
DEMO_PASSWORD = "demo-password-123"  # noqa: S105 - a throwaway local demo login, not a real secret.


class _FixedClock:
    """A `Clock` (see clock.py) that always returns the same instant -
    lets each seeded quote/invoice be backdated to a specific point in the
    last 12 months, going through the real service layer (so numbering,
    status-transition rules, and totals all behave exactly as they would
    for a real user), rather than hand-crafting rows in storage directly."""

    def __init__(self, when: datetime) -> None:
        self._when = when

    def __call__(self) -> datetime:
        return self._when


@dataclass
class _DemoAccount:
    business_name: str
    contact_name: str | None
    email: str
    address_line1: str
    phone: str | None
    address_line2: str | None = None
    town_or_city: str | None = None
    county: str | None = None
    postcode: str | None = None


_NAMED_ACCOUNTS = [
    _DemoAccount(
        "Northwind Traders",
        "Priya Patel",
        "billing@northwindtraders.test",
        "12 Kings Road",
        "020 7946 0958",
        town_or_city="London",
        postcode="SW1A 1AA",
    ),
    _DemoAccount(
        "Blue Harbour Consulting",
        "Tom Ellery",
        "accounts@blueharbour.test",
        "4 Harbour View",
        None,
        address_line2="Floor 2",
        town_or_city="Bristol",
        postcode="BS1 4ST",
    ),
    _DemoAccount(
        "Fenwick & Vale",
        "Sarah Chen",
        "sarah@fenwickvale.test",
        "88 Mill Lane",
        "0161 496 0123",
        town_or_city="Manchester",
        county="Greater Manchester",
        postcode="M1 2WD",
    ),
    _DemoAccount(
        "Orchard Studio",
        None,
        "hello@orchardstudio.test",
        "3 Orchard Court",
        None,
        town_or_city="Leeds",
        postcode="LS1 4DY",
    ),
    _DemoAccount(
        "Camden Digital",
        "Michael Osei",
        "michael@camdendigital.test",
        "27 Camden High St",
        "020 7946 0111",
        town_or_city="London",
        postcode="NW1 7JR",
    ),
]

# Extra accounts, on top of the five named ones above, purely to push the
# accounts list past one page (PAGE_SIZE=20 - see web/src/pages/
# AccountsPage.tsx) so the demo instance actually exercises pagination
# instead of only ever showing a single page. Plain enumerated combinations
# of a name/location/contact below, not randomly generated, so re-running
# `init-db` seeds byte-for-byte the same data every time (see this module's
# idempotency note) - see `_filler_accounts()`.
_FILLER_ACCOUNT_NAMES = [
    "Ashgrove Interiors",
    "Kestrel Media",
    "Thornbury Legal Services",
    "Riverside Bakery",
    "Granite Engineering",
    "Silver Birch Landscaping",
    "Harborview Photography",
    "Meadowfield Architects",
    "Ironbridge Metalworks",
    "Willowmere Events",
    "Cobblestone Coffee Roasters",
    "Lantern Hill Publishing",
    "Oakleaf Accountancy",
    "Brightwater Marine Surveys",
    "Cinderpath Motors",
    "Foxglove Floristry",
    "Hollybank Care Services",
    "Pemberton & Rye",
    "Quayside Boatworks",
    "Redwood Tree Surgery",
]

# (town_or_city, postcode, phone area code) - cycled through for the filler
# accounts, the same UK-city-and-postcode flavour as the five named accounts
# above, without hand-writing a full unique address for each one.
_FILLER_LOCATIONS = [
    ("Bristol", "BS2 0JX", "0117"),
    ("Leeds", "LS2 7HY", "0113"),
    ("Birmingham", "B1 2JX", "0121"),
    ("York", "YO1 6EF", "01904"),
    ("Glasgow", "G1 3AB", "0141"),
    ("Cardiff", "CF10 1EP", "029"),
    ("Newcastle upon Tyne", "NE1 4ST", "0191"),
    ("Nottingham", "NG1 5FS", "0115"),
]

_FILLER_CONTACTS = [
    "Ella Whitfield",
    "Daniel Foster",
    "Amara Okafor",
    "Liam O'Connor",
    "Nadia Hussain",
    "Ben Thackeray",
    "Rosa Alavi",
    "Callum Reid",
]


def _filler_accounts() -> list[_DemoAccount]:
    accounts = []
    for i, name in enumerate(_FILLER_ACCOUNT_NAMES):
        town, postcode, area_code = _FILLER_LOCATIONS[i % len(_FILLER_LOCATIONS)]
        slug = name.lower().replace(" & ", "").replace("'", "").replace(" ", "")
        # Every third one has no contact name/phone, same "not every field
        # is filled in" flavour as Orchard Studio/Riverside Bakery above.
        contact = _FILLER_CONTACTS[i % len(_FILLER_CONTACTS)] if i % 3 != 2 else None
        phone = f"{area_code} 496 0{200 + i}" if i % 2 == 0 else None
        accounts.append(
            _DemoAccount(
                name,
                contact,
                f"hello@{slug}.test",
                f"{i + 10} {town} Road",
                phone,
                town_or_city=town,
                postcode=postcode,
            )
        )
    return accounts


_ACCOUNTS = _NAMED_ACCOUNTS + _filler_accounts()

# (description, quantity, unit_price, tax_rate) - cycled through so the
# demo shows all three UK VAT rates the web UI's dropdown offers.
_LINE_ITEM_POOL: list[tuple[str, Decimal, Decimal, Decimal]] = [
    ("Website design", Decimal("1"), Decimal("1200.00"), Decimal("0.20")),
    ("Consulting (day rate)", Decimal("3"), Decimal("450.00"), Decimal("0.20")),
    ("Copywriting", Decimal("5"), Decimal("80.00"), Decimal("0.20")),
    ("Hosting (annual)", Decimal("1"), Decimal("240.00"), Decimal("0")),
    ("Training workshop", Decimal("1"), Decimal("650.00"), Decimal("0.05")),
    ("Logo design", Decimal("1"), Decimal("350.00"), Decimal("0.20")),
    ("Monthly retainer", Decimal("1"), Decimal("900.00"), Decimal("0.20")),
    ("Print materials", Decimal("200"), Decimal("1.20"), Decimal("0")),
]

DEMO_CURRENCY = "GBP"  # matches the demo profile's reporting currency, so
# the home dashboard's chart picks up every seeded invoice - see CLAUDE.md.

# (description, quantity, unit_price, tax_rate) - expenses recorded against
# an account, shown at the bottom of its detail page (see CLAUDE.md).
_EXPENSE_LINE_ITEM_POOL: list[tuple[str, Decimal, Decimal, Decimal]] = [
    ("Domain renewal", Decimal("1"), Decimal("12.00"), Decimal("0.20")),
    ("Software subscription", Decimal("1"), Decimal("29.00"), Decimal("0.20")),
    ("Stock photography licence", Decimal("3"), Decimal("15.00"), Decimal("0")),
]

# (months_ago, account_index, item_index) - unlike _SCENARIOS below, an
# expense has no draft/sent lifecycle to exercise (see models.Expense), so
# this is just enough spread to show a few EXP-numbered records with
# different accounts/VAT rates on the demo account detail pages.
_EXPENSE_SCENARIOS = [(11, 0, 0), (6, 1, 1), (2, 2, 2)]

# Only the first demo expense gets a receipt attached - enough to show the
# feature off on the account detail page without every seeded expense
# needing one.
_EXPENSE_WITH_RECEIPT_INDEX = 0


def _demo_receipt_pdf(text: str) -> bytes:
    # A minimal synthetic PDF (reportlab - unrelated to pdf.py, which
    # renders via Jinja2/WeasyPrint instead, see its own module docstring)
    # standing in for a scanned receipt - real uploads go through
    # ExpenseService.add_attachment exactly the same way a real user's
    # would, just with generated bytes instead of a file picked in the
    # browser.
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=text)
    doc.build([Paragraph(text, getSampleStyleSheet()["Normal"])])
    return buffer.getvalue()


def _months_ago(now: datetime, months: int) -> datetime:
    # A fixed days-ago offset from `now`, not calendar-month stepping to a
    # fixed day of the month - "the 12th of N months ago" can land in the
    # *future* when today is early in the month (e.g. today the 3rd, this
    # month's 12th hasn't happened yet), which would silently produce a
    # not-actually-backdated "historical" invoice. Days-ago is always
    # safely in the past, and still spreads scenarios across ~12 distinct
    # calendar months since each step is ~30 days.
    return now - timedelta(days=30 * months + 3)


def _add_line_items(quotes: QuoteService, organisation_id: str, quote_id: str, *item_indices: int) -> None:
    for i in item_indices:
        description, quantity, unit_price, tax_rate = _LINE_ITEM_POOL[i % len(_LINE_ITEM_POOL)]
        quotes.add_line_item(
            organisation_id,
            quote_id,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            tax_rate=tax_rate,
        )


@dataclass
class _Scenario:
    months_ago: int
    account_index: int
    run: str  # method name on _Seeder, for a flat, readable table below


class _Seeder:
    """One instance per seeded quote/invoice - services here are always
    built with a `_FixedClock` for a specific historical `when`, so
    `issue_date`/`created_at` land in the right month regardless of when
    `init-db` actually runs."""

    def __init__(
        self, application: Application, organisation_id: str, account_id: str, when: datetime, item_index: int
    ) -> None:
        clock = _FixedClock(when)
        self.repository = application.repository
        self.quotes = QuoteService(self.repository, clock=clock)
        self.invoices = InvoiceService(self.repository, clock=clock)
        self.organisation_id = organisation_id
        self.account_id = account_id
        self.item_index = item_index

    def _new_quote(self) -> str:
        quote = self.quotes.create_quote(
            organisation_id=self.organisation_id, account_id=self.account_id, currency=DEMO_CURRENCY
        )
        _add_line_items(self.quotes, self.organisation_id, quote.id, self.item_index, self.item_index + 1)
        return quote.id

    def draft_quote(self) -> None:
        self._new_quote()

    def sent_quote(self) -> None:
        self.quotes.send(self.organisation_id, self._new_quote())

    def rejected_quote(self) -> None:
        quote_id = self._new_quote()
        self.quotes.send(self.organisation_id, quote_id)
        self.quotes.mark_rejected(self.organisation_id, quote_id)

    def expired_quote(self) -> None:
        quote_id = self._new_quote()
        self.quotes.send(self.organisation_id, quote_id)
        self.quotes.mark_expired(self.organisation_id, quote_id)

    def _accepted_and_converted(self) -> str:
        quote_id = self._new_quote()
        self.quotes.send(self.organisation_id, quote_id)
        self.quotes.mark_accepted(self.organisation_id, quote_id)
        return self.quotes.convert_to_invoice(self.organisation_id, quote_id).id

    def draft_invoice(self) -> None:
        self._accepted_and_converted()

    def outstanding_invoice(self) -> None:
        invoice_id = self._accepted_and_converted()
        # Generous payment terms, not the usual 30 - this scenario is only
        # ever scheduled a few weeks back at most (see _SCENARIOS), and
        # needs to stay reliably not-yet-due regardless of which exact day
        # `init-db` runs on.
        self.invoices.send(self.organisation_id, invoice_id, payment_terms_days=60)

    def overdue_invoice(self) -> None:
        invoice_id = self._accepted_and_converted()
        self.invoices.send(self.organisation_id, invoice_id, payment_terms_days=14)

    def paid_invoice(self) -> None:
        invoice_id = self._accepted_and_converted()
        self.invoices.send(self.organisation_id, invoice_id, payment_terms_days=14)
        self.invoices.pay(self.organisation_id, invoice_id)

    def void_invoice(self) -> None:
        invoice_id = self._accepted_and_converted()
        self.invoices.send(self.organisation_id, invoice_id, payment_terms_days=14)
        self.invoices.void(self.organisation_id, invoice_id)


# Spread across the last 12 months (11 = a year ago, 0 = this month).
# `overdue_invoice` is pinned far enough back, and `outstanding_invoice`
# close enough to now, that both stay true regardless of exactly which day
# `init-db` runs on.
_CURATED_SCENARIOS = [
    _Scenario(11, 0, "draft_quote"),
    _Scenario(10, 1, "sent_quote"),
    _Scenario(10, 2, "overdue_invoice"),
    _Scenario(9, 3, "rejected_quote"),
    _Scenario(8, 4, "paid_invoice"),
    _Scenario(7, 0, "expired_quote"),
    _Scenario(6, 1, "void_invoice"),
    _Scenario(5, 2, "paid_invoice"),
    _Scenario(4, 3, "draft_invoice"),
    _Scenario(3, 4, "sent_quote"),
    _Scenario(2, 0, "paid_invoice"),
    _Scenario(1, 1, "outstanding_invoice"),
    _Scenario(0, 2, "outstanding_invoice"),
    _Scenario(0, 3, "draft_quote"),
]

# One invoice-producing scenario per filler account (see _filler_accounts)
# - on top of the fourteen curated ones above, enough to push both the
# quotes and invoices lists past one page too (PAGE_SIZE=20 - see
# web/src/pages/QuotesPage.tsx/InvoicesPage.tsx), the same reasoning as the
# filler accounts themselves. Deliberately only draft/paid/void outcomes,
# not overdue/outstanding - those two are timing-sensitive (a "sent"
# invoice's due date has to land on the right side of today - see
# outstanding_invoice/overdue_invoice above), the fourteen curated
# scenarios already guarantee at least one of each, and spreading more of
# them across a full year here without the same care about `months_ago`
# could silently mislabel one (e.g. an "overdue" invoice that isn't
# actually overdue yet).
_FILLER_INVOICE_TYPES = ["draft_invoice", "paid_invoice", "void_invoice"]

_SCENARIOS = _CURATED_SCENARIOS + [
    _Scenario(i % 12, len(_NAMED_ACCOUNTS) + i, _FILLER_INVOICE_TYPES[i % len(_FILLER_INVOICE_TYPES)])
    for i in range(len(_FILLER_ACCOUNT_NAMES))
]


def seed_demo_data(application: Application, auth: Auth, *, now: datetime | None = None) -> bool:
    """Seeds the demo login user, business profile, accounts, and a
    12-month spread of quotes/invoices. Returns False (no-op) if the demo
    user already exists - safe to call on every `init-db`. `now` is the
    reference point everything is backdated from (defaults to the real
    time); tests pass a fixed value so "is this invoice overdue yet"
    assertions don't depend on which day the suite happens to run."""
    try:
        user = auth.service.create_user(DEMO_EMAIL, DEMO_PASSWORD, name="Demo User")
    except DuplicateUser:
        return False

    now = now or datetime.now(UTC)
    business_name = "Blake Freelance Design"
    organisation_id = OrganisationService(application.repository, clock=lambda: now).get_or_create_for_user(
        user.id, default_name=business_name
    )

    BusinessProfileService(application.repository, clock=lambda: now).save_profile(
        user.id,
        title="Ms",
        first_name="Jordan",
        last_name="Blake",
        business_name=business_name,
        address_line1="15 Riverside Walk",
        town_or_city="London",
        postcode="E1 6AN",
        payment_terms_days=30,
        currency=DEMO_CURRENCY,
        utr="1234567890",
        vat_number="GB123456789",
        bank_account_name="Blake Freelance Design",
        bank_sort_code="12-34-56",
        bank_account_number="12345678",
        # Deliberately different per document type, not the same text three
        # times over - that's the whole point of these being three
        # independent pairs rather than one shared one (see CLAUDE.md).
        quote_document_header="Blake Freelance Design",
        quote_document_footer="This quote is valid for 30 days from the issue date.",
        invoice_document_header="Blake Freelance Design\nRegistered in England & Wales, company no. 12345678",
        invoice_document_footer="Thank you for your business!\nPayment is due within the stated terms.",
        expense_document_header="Blake Freelance Design",
        expense_document_footer="Recorded for internal accounting purposes only.",
        # Shows off the accent-colour feature in the seeded PDFs rather than
        # leaving it at the neutral default every never-customised profile
        # gets (see pdf.py's _ACCENT_FALLBACK).
        accent_color="#2563EB",
    )

    accounts = AccountService(application.repository, clock=lambda: now)
    account_ids = [
        accounts.create_account(
            organisation_id=organisation_id,
            business_name=a.business_name,
            email=a.email,
            address_line1=a.address_line1,
            contact_name=a.contact_name,
            phone=a.phone,
            address_line2=a.address_line2,
            town_or_city=a.town_or_city,
            county=a.county,
            postcode=a.postcode,
        ).id
        for a in _ACCOUNTS
    ]

    # A couple of domains, on a couple of accounts - not every account has
    # one, same "not every account needs every kind of child record" spirit
    # as expenses/attachments below. One expiring soon (auto-renew on, so
    # nothing to actually do) and one already lapsed (auto-renew off - the
    # case actually worth flagging), rather than only ever showing
    # comfortably-far-off dates.
    domains = DomainService(application.repository, clock=lambda: now)
    domains.create_domain(
        organisation_id,
        account_ids[0],
        domain_name="northwindtraders.test",
        expiry_date=(now + timedelta(days=18)).date(),
        registrar="123-Reg",
        auto_renew=True,
    )
    domains.create_domain(
        organisation_id,
        account_ids[1],
        domain_name="blueharbourconsulting.test",
        expiry_date=(now - timedelta(days=9)).date(),
        registrar="GoDaddy",
        auto_renew=False,
    )

    for scenario in _SCENARIOS:
        seeder = _Seeder(
            application,
            organisation_id=organisation_id,
            account_id=account_ids[scenario.account_index],
            when=_months_ago(now, scenario.months_ago),
            item_index=scenario.account_index,
        )
        getattr(seeder, scenario.run)()

    for scenario_index, (months_ago, account_index, item_index) in enumerate(_EXPENSE_SCENARIOS):
        expenses = ExpenseService(
            application.repository,
            clock=_FixedClock(_months_ago(now, months_ago)),
            attachments=application.attachment_store,
        )
        expense = expenses.create_expense(
            organisation_id=organisation_id,
            account_id=account_ids[account_index],
            currency=DEMO_CURRENCY,
        )
        description, quantity, unit_price, tax_rate = _EXPENSE_LINE_ITEM_POOL[item_index]
        expenses.add_line_item(
            organisation_id,
            expense.id,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            tax_rate=tax_rate,
        )
        if scenario_index == _EXPENSE_WITH_RECEIPT_INDEX:
            expenses.add_attachment(
                organisation_id,
                expense.id,
                filename="receipt.pdf",
                content_type="application/pdf",
                data=_demo_receipt_pdf(f"Receipt for {description}"),
            )

    return True
