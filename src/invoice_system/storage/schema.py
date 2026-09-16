# Forward-only migrations. Never edit an entry once it has shipped -
# append a new one instead. Applied in order, tracked via PRAGMA user_version.
#
# Flattened to a single baseline on 2026-09-16: no real database had been
# started against the previous 5-migration history yet, so there was no
# existing data any later migration needed to carry forward - see CLAUDE.md.
# From here on, a schema change is a new entry appended to this list, not an
# edit to the one below.
MIGRATIONS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_name TEXT NOT NULL,
        contact_name TEXT,
        email TEXT NOT NULL,
        phone TEXT,
        address TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL REFERENCES accounts(id),
        number TEXT UNIQUE,
        status TEXT NOT NULL,
        currency TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        expiry_date TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS quote_line_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_id INTEGER NOT NULL REFERENCES quotes(id),
        description TEXT NOT NULL,
        quantity TEXT NOT NULL,
        unit_price TEXT NOT NULL,
        position INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL REFERENCES accounts(id),
        quote_id INTEGER REFERENCES quotes(id),
        number TEXT UNIQUE,
        status TEXT NOT NULL,
        currency TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        due_date TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS invoice_line_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL REFERENCES invoices(id),
        description TEXT NOT NULL,
        quantity TEXT NOT NULL,
        unit_price TEXT NOT NULL,
        position INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS counters (
        name TEXT PRIMARY KEY,
        value INTEGER NOT NULL
    );

    -- user_id is sessionkit's User.id - a plain column, not an enforced
    -- foreign key, since it lives in a separate SQLite file/database. See
    -- CLAUDE.md and data-model.md for why, and the orphaning consequence.
    --
    -- title/address_line1/address_line2/town_or_city/county/postcode/utr/
    -- vat_number are each independently optional (nullable, no "all or
    -- nothing" rule); first_name/last_name/business_name are required
    -- (NOT NULL DEFAULT '', enforced as non-blank in BusinessProfileService,
    -- never in storage). address_line1/2/town_or_city/county/postcode follow
    -- the UK GOV.UK Design System's standard address pattern. currency is
    -- the *reporting* currency the home dashboard's monthly-totals chart
    -- sums in, independent of the currency chosen per quote/invoice.
    CREATE TABLE IF NOT EXISTS business_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        title TEXT,
        first_name TEXT NOT NULL DEFAULT '',
        last_name TEXT NOT NULL DEFAULT '',
        business_name TEXT NOT NULL DEFAULT '',
        address_line1 TEXT,
        address_line2 TEXT,
        town_or_city TEXT,
        county TEXT,
        postcode TEXT,
        payment_terms_days INTEGER NOT NULL DEFAULT 30,
        currency TEXT NOT NULL DEFAULT 'GBP',
        utr TEXT,
        vat_number TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
]
