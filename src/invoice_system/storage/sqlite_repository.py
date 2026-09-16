import sqlite3
import threading
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..models import (
    Account,
    BusinessProfile,
    Invoice,
    InvoiceStatus,
    LineItem,
    Organisation,
    Quote,
    QuoteStatus,
)
from .schema import MIGRATIONS


class SqliteRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    def close(self) -> None:
        self._conn.close()

    def migrate(self) -> None:
        with self._lock:
            current = self._conn.execute("PRAGMA user_version").fetchone()[0]
            for version, script in enumerate(MIGRATIONS, start=1):
                if version <= current:
                    continue
                self._conn.executescript(script)
                self._conn.execute(f"PRAGMA user_version = {version}")
            self._conn.commit()

    # -- Organisations ---------------------------------------------------------

    def get_organisation_id_for_user(self, user_id: int) -> int | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT organisation_id FROM organisation_members WHERE user_id = ?", (user_id,)
            ).fetchone()
        return row["organisation_id"] if row else None

    def create_organisation(self, organisation: Organisation) -> Organisation:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO organisations (name, created_at) VALUES (?, ?)",
                (organisation.name, organisation.created_at.isoformat()),
            )
            self._conn.commit()
            organisation.id = cur.lastrowid
            return organisation

    def add_organisation_member(self, organisation_id: int, user_id: int) -> int:
        # Check-then-insert, but atomic under the single shared-connection
        # lock (see CLAUDE.md) rather than two separate locked calls - two
        # concurrent first-ever requests for the same brand-new user would
        # otherwise both pass OrganisationService's initial "does this user
        # have an organisation" check, then race here: without this being
        # one atomic operation, the loser's plain INSERT would violate
        # organisation_members.user_id's UNIQUE constraint and crash the
        # request instead of just returning the winner's organisation_id
        # (the Organisation row it built is left an orphan, matching this
        # method's docstring on models.Organisation - harmless, since
        # nothing ever looks up an Organisation except via its members).
        with self._lock:
            row = self._conn.execute(
                "SELECT organisation_id FROM organisation_members WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row is not None:
                return row["organisation_id"]
            self._conn.execute(
                "INSERT INTO organisation_members (organisation_id, user_id, created_at) VALUES (?, ?, ?)",
                (organisation_id, user_id, datetime.now().astimezone().isoformat()),
            )
            self._conn.commit()
            return organisation_id

    # -- Accounts ----------------------------------------------------------

    def create_account(self, account: Account) -> Account:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO accounts (organisation_id, business_name, contact_name, email, phone, "
                "address, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    account.organisation_id,
                    account.business_name,
                    account.contact_name,
                    account.email,
                    account.phone,
                    account.address,
                    account.created_at.isoformat(),
                ),
            )
            self._conn.commit()
            account.id = cur.lastrowid
            return account

    def get_account(self, organisation_id: int, account_id: int) -> Account | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM accounts WHERE id = ? AND organisation_id = ?", (account_id, organisation_id)
            ).fetchone()
        return self._row_to_account(row) if row else None

    def list_accounts(self, organisation_id: int) -> list[Account]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM accounts WHERE organisation_id = ? ORDER BY id", (organisation_id,)
            ).fetchall()
        return [self._row_to_account(row) for row in rows]

    def update_account(self, account: Account) -> Account:
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET business_name = ?, contact_name = ?, email = ?, phone = ?, "
                "address = ? WHERE id = ? AND organisation_id = ?",
                (
                    account.business_name,
                    account.contact_name,
                    account.email,
                    account.phone,
                    account.address,
                    account.id,
                    account.organisation_id,
                ),
            )
            self._conn.commit()
            return account

    @staticmethod
    def _row_to_account(row: sqlite3.Row) -> Account:
        return Account(
            id=row["id"],
            organisation_id=row["organisation_id"],
            business_name=row["business_name"],
            contact_name=row["contact_name"],
            email=row["email"],
            phone=row["phone"],
            address=row["address"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # -- Business profiles -----------------------------------------------------

    def get_business_profile(self, user_id: int) -> BusinessProfile | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM business_profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
        return self._row_to_business_profile(row) if row else None

    def upsert_business_profile(self, profile: BusinessProfile) -> BusinessProfile:
        with self._lock:
            self._conn.execute(
                "INSERT INTO business_profiles (user_id, title, first_name, last_name, "
                "business_name, address_line1, address_line2, town_or_city, county, postcode, "
                "payment_terms_days, currency, utr, vat_number, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "title = excluded.title, "
                "first_name = excluded.first_name, "
                "last_name = excluded.last_name, "
                "business_name = excluded.business_name, "
                "address_line1 = excluded.address_line1, "
                "address_line2 = excluded.address_line2, "
                "town_or_city = excluded.town_or_city, "
                "county = excluded.county, "
                "postcode = excluded.postcode, "
                "payment_terms_days = excluded.payment_terms_days, "
                "currency = excluded.currency, "
                "utr = excluded.utr, "
                "vat_number = excluded.vat_number, "
                "updated_at = excluded.updated_at",
                (
                    profile.user_id,
                    profile.title,
                    profile.first_name,
                    profile.last_name,
                    profile.business_name,
                    profile.address_line1,
                    profile.address_line2,
                    profile.town_or_city,
                    profile.county,
                    profile.postcode,
                    profile.payment_terms_days,
                    profile.currency,
                    profile.utr,
                    profile.vat_number,
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM business_profiles WHERE user_id = ?", (profile.user_id,)
            ).fetchone()
        return self._row_to_business_profile(row)

    @staticmethod
    def _row_to_business_profile(row: sqlite3.Row) -> BusinessProfile:
        return BusinessProfile(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            business_name=row["business_name"],
            address_line1=row["address_line1"],
            address_line2=row["address_line2"],
            town_or_city=row["town_or_city"],
            county=row["county"],
            postcode=row["postcode"],
            payment_terms_days=row["payment_terms_days"],
            currency=row["currency"],
            utr=row["utr"],
            vat_number=row["vat_number"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # -- Quotes --------------------------------------------------------------

    def create_quote(self, quote: Quote) -> Quote:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO quotes (organisation_id, account_id, number, status, currency, issue_date, "
                "expiry_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    quote.organisation_id,
                    quote.account_id,
                    quote.number,
                    quote.status.value,
                    quote.currency,
                    quote.issue_date.isoformat(),
                    quote.expiry_date.isoformat() if quote.expiry_date else None,
                    quote.created_at.isoformat(),
                ),
            )
            self._conn.commit()
            quote.id = cur.lastrowid
            return quote

    def get_quote(self, organisation_id: int, quote_id: int) -> Quote | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM quotes WHERE id = ? AND organisation_id = ?", (quote_id, organisation_id)
            ).fetchone()
            if row is None:
                return None
            item_rows = self._conn.execute(
                "SELECT * FROM quote_line_items WHERE quote_id = ? ORDER BY position", (quote_id,)
            ).fetchall()
        return self._row_to_quote(row, item_rows)

    def list_quotes(self, organisation_id: int, account_id: int | None = None) -> list[Quote]:
        with self._lock:
            if account_id is None:
                rows = self._conn.execute(
                    "SELECT * FROM quotes WHERE organisation_id = ? ORDER BY id", (organisation_id,)
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM quotes WHERE organisation_id = ? AND account_id = ? ORDER BY id",
                    (organisation_id, account_id),
                ).fetchall()
            quotes = []
            for row in rows:
                item_rows = self._conn.execute(
                    "SELECT * FROM quote_line_items WHERE quote_id = ? ORDER BY position", (row["id"],)
                ).fetchall()
                quotes.append(self._row_to_quote(row, item_rows))
        return quotes

    def update_quote(self, quote: Quote) -> Quote:
        with self._lock:
            self._conn.execute(
                "UPDATE quotes SET number = ?, status = ?, currency = ?, issue_date = ?, expiry_date = ? "
                "WHERE id = ? AND organisation_id = ?",
                (
                    quote.number,
                    quote.status.value,
                    quote.currency,
                    quote.issue_date.isoformat(),
                    quote.expiry_date.isoformat() if quote.expiry_date else None,
                    quote.id,
                    quote.organisation_id,
                ),
            )
            self._conn.commit()
            return quote

    def add_quote_line_item(self, quote_id: int, item: LineItem) -> LineItem:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO quote_line_items "
                "(quote_id, description, quantity, unit_price, tax_rate, position) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    quote_id,
                    item.description,
                    str(item.quantity),
                    str(item.unit_price),
                    str(item.tax_rate),
                    item.position,
                ),
            )
            self._conn.commit()
            item.id = cur.lastrowid
            return item

    def next_quote_number(self, organisation_id: int) -> str:
        return self._next_number(f"{organisation_id}:quote", "Q-")

    @staticmethod
    def _row_to_quote(row: sqlite3.Row, item_rows: list[sqlite3.Row]) -> Quote:
        return Quote(
            id=row["id"],
            organisation_id=row["organisation_id"],
            account_id=row["account_id"],
            number=row["number"],
            status=QuoteStatus(row["status"]),
            currency=row["currency"],
            issue_date=date.fromisoformat(row["issue_date"]),
            expiry_date=date.fromisoformat(row["expiry_date"]) if row["expiry_date"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            line_items=[SqliteRepository._row_to_line_item(r) for r in item_rows],
        )

    # -- Invoices --------------------------------------------------------------

    def create_invoice(self, invoice: Invoice) -> Invoice:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO invoices (organisation_id, account_id, quote_id, number, status, currency, "
                "issue_date, due_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    invoice.organisation_id,
                    invoice.account_id,
                    invoice.quote_id,
                    invoice.number,
                    invoice.status.value,
                    invoice.currency,
                    invoice.issue_date.isoformat(),
                    invoice.due_date.isoformat() if invoice.due_date else None,
                    invoice.created_at.isoformat(),
                ),
            )
            self._conn.commit()
            invoice.id = cur.lastrowid
            return invoice

    def get_invoice(self, organisation_id: int, invoice_id: int) -> Invoice | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM invoices WHERE id = ? AND organisation_id = ?",
                (invoice_id, organisation_id),
            ).fetchone()
            if row is None:
                return None
            item_rows = self._conn.execute(
                "SELECT * FROM invoice_line_items WHERE invoice_id = ? ORDER BY position", (invoice_id,)
            ).fetchall()
        return self._row_to_invoice(row, item_rows)

    def list_invoices(self, organisation_id: int, account_id: int | None = None) -> list[Invoice]:
        with self._lock:
            if account_id is None:
                rows = self._conn.execute(
                    "SELECT * FROM invoices WHERE organisation_id = ? ORDER BY id", (organisation_id,)
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM invoices WHERE organisation_id = ? AND account_id = ? ORDER BY id",
                    (organisation_id, account_id),
                ).fetchall()
            invoices = []
            for row in rows:
                item_rows = self._conn.execute(
                    "SELECT * FROM invoice_line_items WHERE invoice_id = ? ORDER BY position", (row["id"],)
                ).fetchall()
                invoices.append(self._row_to_invoice(row, item_rows))
        return invoices

    def update_invoice(self, invoice: Invoice) -> Invoice:
        with self._lock:
            self._conn.execute(
                "UPDATE invoices SET number = ?, status = ?, currency = ?, issue_date = ?, due_date = ? "
                "WHERE id = ? AND organisation_id = ?",
                (
                    invoice.number,
                    invoice.status.value,
                    invoice.currency,
                    invoice.issue_date.isoformat(),
                    invoice.due_date.isoformat() if invoice.due_date else None,
                    invoice.id,
                    invoice.organisation_id,
                ),
            )
            self._conn.commit()
            return invoice

    def add_invoice_line_item(self, invoice_id: int, item: LineItem) -> LineItem:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO invoice_line_items "
                "(invoice_id, description, quantity, unit_price, tax_rate, position) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    invoice_id,
                    item.description,
                    str(item.quantity),
                    str(item.unit_price),
                    str(item.tax_rate),
                    item.position,
                ),
            )
            self._conn.commit()
            item.id = cur.lastrowid
            return item

    def next_invoice_number(self, organisation_id: int) -> str:
        return self._next_number(f"{organisation_id}:invoice", "INV-")

    @staticmethod
    def _row_to_invoice(row: sqlite3.Row, item_rows: list[sqlite3.Row]) -> Invoice:
        return Invoice(
            id=row["id"],
            organisation_id=row["organisation_id"],
            account_id=row["account_id"],
            quote_id=row["quote_id"],
            number=row["number"],
            status=InvoiceStatus(row["status"]),
            currency=row["currency"],
            issue_date=date.fromisoformat(row["issue_date"]),
            due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            line_items=[SqliteRepository._row_to_line_item(r) for r in item_rows],
        )

    @staticmethod
    def _row_to_line_item(row: sqlite3.Row) -> LineItem:
        return LineItem(
            id=row["id"],
            description=row["description"],
            quantity=Decimal(row["quantity"]),
            unit_price=Decimal(row["unit_price"]),
            tax_rate=Decimal(row["tax_rate"]),
            position=row["position"],
        )

    # -- Shared --------------------------------------------------------------

    def _next_number(self, name: str, prefix: str) -> str:
        # `name` is "<organisation_id>:quote"/"<organisation_id>:invoice",
        # not just "quote"/"invoice" - each organisation gets its own
        # independent Q-0001/INV-0001 sequence starting from one, rather
        # than a single global counter that would leak how many
        # quotes/invoices *other* organisations have created (their own
        # numbers jumping straight to Q-0047 on their very first quote).
        # No schema change needed for this - `counters.name` was already a
        # free-text key, not literally constrained to "quote"/"invoice".
        with self._lock:
            row = self._conn.execute("SELECT value FROM counters WHERE name = ?", (name,)).fetchone()
            value = (row["value"] if row else 0) + 1
            self._conn.execute(
                "INSERT INTO counters (name, value) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET value = excluded.value",
                (name, value),
            )
            self._conn.commit()
        return f"{prefix}{value:04d}"
