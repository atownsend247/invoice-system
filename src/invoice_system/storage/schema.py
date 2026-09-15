# Forward-only migrations. Never edit an entry once it has shipped -
# append a new one instead. Applied in order, tracked via PRAGMA user_version.
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
    """,
    """
    -- user_id is sessionkit's User.id - a plain column, not an enforced
    -- foreign key, since it lives in a separate SQLite file/database. See
    -- CLAUDE.md and data-model.md for why, and the orphaning consequence.
    CREATE TABLE IF NOT EXISTS business_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        business_name TEXT NOT NULL DEFAULT '',
        business_address TEXT NOT NULL DEFAULT '',
        payment_terms_days INTEGER NOT NULL DEFAULT 30,
        utr TEXT,
        vat_number TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    """
    -- Adds title/first_name/last_name and relaxes business_address to
    -- optional. SQLite can't ALTER a column's NOT NULL constraint in place,
    -- so this is the documented rebuild-and-swap: new table, copy existing
    -- rows across (NULLIF turns any stored '' address into a real NULL,
    -- matching what "optional" means for every other nullable field here),
    -- drop the old table, rename the new one into its place.
    CREATE TABLE business_profiles_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        title TEXT,
        first_name TEXT NOT NULL DEFAULT '',
        last_name TEXT NOT NULL DEFAULT '',
        business_name TEXT NOT NULL DEFAULT '',
        business_address TEXT,
        payment_terms_days INTEGER NOT NULL DEFAULT 30,
        utr TEXT,
        vat_number TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    INSERT INTO business_profiles_new
        (id, user_id, business_name, business_address, payment_terms_days,
         utr, vat_number, created_at, updated_at)
    SELECT id, user_id, business_name, NULLIF(business_address, ''), payment_terms_days,
           utr, vat_number, created_at, updated_at
    FROM business_profiles;

    DROP TABLE business_profiles;
    ALTER TABLE business_profiles_new RENAME TO business_profiles;
    """,
    """
    -- Splits the single business_address into UK GOV.UK Design System-style
    -- address fields (address_line1/2, town_or_city, county, postcode) -
    -- see CLAUDE.md and data-model.md. Unlike migration 3, this doesn't need
    -- a rebuild-and-swap: adding nullable columns and dropping a nullable
    -- one are both plain ALTER TABLE operations SQLite supports directly.
    -- The old free-text address can't be parsed into structured fields
    -- automatically, so existing data moves into address_line1 rather than
    -- being silently dropped - a person can re-split it themselves next
    -- time they visit Settings.
    ALTER TABLE business_profiles ADD COLUMN address_line1 TEXT;
    ALTER TABLE business_profiles ADD COLUMN address_line2 TEXT;
    ALTER TABLE business_profiles ADD COLUMN town_or_city TEXT;
    ALTER TABLE business_profiles ADD COLUMN county TEXT;
    ALTER TABLE business_profiles ADD COLUMN postcode TEXT;

    UPDATE business_profiles SET address_line1 = business_address WHERE business_address IS NOT NULL;

    ALTER TABLE business_profiles DROP COLUMN business_address;
    """,
    """
    -- Adds a reporting currency to business_profiles (see CLAUDE.md and
    -- data-model.md: this is the currency the home dashboard's monthly
    -- totals are summed in, independent of the currency chosen per
    -- quote/invoice). A constant-default ADD COLUMN is a plain ALTER TABLE
    -- SQLite supports directly, like migration 4 - no rebuild needed.
    ALTER TABLE business_profiles ADD COLUMN currency TEXT NOT NULL DEFAULT 'GBP';
    """,
]
