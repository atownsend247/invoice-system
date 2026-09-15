import sqlite3
import threading
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..models import Account, BusinessProfile, Invoice, InvoiceStatus, LineItem, Quote, QuoteStatus
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

    # -- Accounts ----------------------------------------------------------

    def create_account(self, account: Account) -> Account:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO accounts (business_name, contact_name, email, phone, address, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
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

    def get_account(self, account_id: int) -> Account | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return self._row_to_account(row) if row else None

    def list_accounts(self) -> list[Account]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
        return [self._row_to_account(row) for row in rows]

    @staticmethod
    def _row_to_account(row: sqlite3.Row) -> Account:
        return Account(
            id=row["id"],
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
                "INSERT INTO business_profiles (user_id, business_name, business_address, "
                "payment_terms_days, utr, vat_number, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "business_name = excluded.business_name, "
                "business_address = excluded.business_address, "
                "payment_terms_days = excluded.payment_terms_days, "
                "utr = excluded.utr, "
                "vat_number = excluded.vat_number, "
                "updated_at = excluded.updated_at",
                (
                    profile.user_id,
                    profile.business_name,
                    profile.business_address,
                    profile.payment_terms_days,
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
            business_name=row["business_name"],
            business_address=row["business_address"],
            payment_terms_days=row["payment_terms_days"],
            utr=row["utr"],
            vat_number=row["vat_number"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # -- Quotes --------------------------------------------------------------

    def create_quote(self, quote: Quote) -> Quote:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO quotes (account_id, number, status, currency, issue_date, expiry_date, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
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

    def get_quote(self, quote_id: int) -> Quote | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
            if row is None:
                return None
            item_rows = self._conn.execute(
                "SELECT * FROM quote_line_items WHERE quote_id = ? ORDER BY position", (quote_id,)
            ).fetchall()
        return self._row_to_quote(row, item_rows)

    def list_quotes(self, account_id: int | None = None) -> list[Quote]:
        with self._lock:
            if account_id is None:
                rows = self._conn.execute("SELECT * FROM quotes ORDER BY id").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM quotes WHERE account_id = ? ORDER BY id", (account_id,)
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
                "WHERE id = ?",
                (
                    quote.number,
                    quote.status.value,
                    quote.currency,
                    quote.issue_date.isoformat(),
                    quote.expiry_date.isoformat() if quote.expiry_date else None,
                    quote.id,
                ),
            )
            self._conn.commit()
            return quote

    def add_quote_line_item(self, quote_id: int, item: LineItem) -> LineItem:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO quote_line_items (quote_id, description, quantity, unit_price, position) "
                "VALUES (?, ?, ?, ?, ?)",
                (quote_id, item.description, str(item.quantity), str(item.unit_price), item.position),
            )
            self._conn.commit()
            item.id = cur.lastrowid
            return item

    def next_quote_number(self) -> str:
        return self._next_number("quote", "Q-")

    @staticmethod
    def _row_to_quote(row: sqlite3.Row, item_rows: list[sqlite3.Row]) -> Quote:
        return Quote(
            id=row["id"],
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
                "INSERT INTO invoices (account_id, quote_id, number, status, currency, issue_date, "
                "due_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
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

    def get_invoice(self, invoice_id: int) -> Invoice | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if row is None:
                return None
            item_rows = self._conn.execute(
                "SELECT * FROM invoice_line_items WHERE invoice_id = ? ORDER BY position", (invoice_id,)
            ).fetchall()
        return self._row_to_invoice(row, item_rows)

    def list_invoices(self, account_id: int | None = None) -> list[Invoice]:
        with self._lock:
            if account_id is None:
                rows = self._conn.execute("SELECT * FROM invoices ORDER BY id").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM invoices WHERE account_id = ? ORDER BY id", (account_id,)
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
                "WHERE id = ?",
                (
                    invoice.number,
                    invoice.status.value,
                    invoice.currency,
                    invoice.issue_date.isoformat(),
                    invoice.due_date.isoformat() if invoice.due_date else None,
                    invoice.id,
                ),
            )
            self._conn.commit()
            return invoice

    def add_invoice_line_item(self, invoice_id: int, item: LineItem) -> LineItem:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO invoice_line_items (invoice_id, description, quantity, unit_price, position) "
                "VALUES (?, ?, ?, ?, ?)",
                (invoice_id, item.description, str(item.quantity), str(item.unit_price), item.position),
            )
            self._conn.commit()
            item.id = cur.lastrowid
            return item

    def next_invoice_number(self) -> str:
        return self._next_number("invoice", "INV-")

    @staticmethod
    def _row_to_invoice(row: sqlite3.Row, item_rows: list[sqlite3.Row]) -> Invoice:
        return Invoice(
            id=row["id"],
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
            position=row["position"],
        )

    # -- Shared --------------------------------------------------------------

    def _next_number(self, name: str, prefix: str) -> str:
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
