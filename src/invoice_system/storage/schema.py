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
    """
    -- Per-line VAT/tax rate (a fraction, e.g. '0.20' for 20% - see
    -- CLAUDE.md and data-model.md). Different lines on the same
    -- quote/invoice can legitimately carry different UK VAT rates
    -- (standard/reduced/zero), so this lives on the line item, not the
    -- quote/invoice as a whole. A constant-default ADD COLUMN is a plain
    -- ALTER TABLE SQLite supports directly - every existing line item is
    -- backfilled to '0' (no tax), leaving its total unchanged.
    ALTER TABLE quote_line_items ADD COLUMN tax_rate TEXT NOT NULL DEFAULT '0';
    ALTER TABLE invoice_line_items ADD COLUMN tax_rate TEXT NOT NULL DEFAULT '0';
    """,
    """
    -- The tenant boundary - see CLAUDE.md and models.py's Organisation
    -- docstring. user_id is sessionkit's User.id, same cross-database
    -- plain-column reasoning as business_profiles.user_id: not an
    -- enforced FK, lives in the separate auth.db. UNIQUE on user_id
    -- enforces "one organisation per user" for now; multiple users
    -- sharing one organisation later means dropping that constraint, not
    -- restructuring this table.
    CREATE TABLE IF NOT EXISTS organisations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS organisation_members (
        organisation_id INTEGER NOT NULL REFERENCES organisations(id),
        user_id INTEGER NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        PRIMARY KEY (organisation_id, user_id)
    );

    -- Nullable, not NOT NULL - there's no meaningful default organisation
    -- to backfill existing rows with (unlike migration 2's tax_rate),  and
    -- SQLite can't add a NOT NULL column without one. A pre-migration row
    -- keeps NULL and becomes invisible under the new per-organisation
    -- scoping (nothing dereferences accounts.organisation_id and hopes for
    -- a real Organisation without going through that scoping first) - see
    -- CLAUDE.md for why this was a deliberate "reseed, don't migrate"
    -- choice rather than guessing which user should adopt old rows.
    ALTER TABLE accounts ADD COLUMN organisation_id INTEGER;
    ALTER TABLE quotes ADD COLUMN organisation_id INTEGER;
    ALTER TABLE invoices ADD COLUMN organisation_id INTEGER;
    """,
    """
    -- Q-0001/INV-0001 are now per-organisation (see migration 3 and
    -- next_quote_number/next_invoice_number's per-organisation counter
    -- key) - two organisations' first quote/invoice can legitimately
    -- both be "Q-0001"/"INV-0001". The column-level UNIQUE on
    -- quotes.number/invoices.number from the original baseline is now
    -- wrong (globally unique), but SQLite can't ALTER a column to drop a
    -- UNIQUE constraint - this is a rebuild-and-swap, same pattern as the
    -- CLAUDE.md-documented migration that relaxed a NOT NULL. Row ids are
    -- carried across explicitly so invoice_line_items/quote_line_items
    -- (and invoices.quote_id) keep pointing at the same rows. A
    -- composite UNIQUE index on (organisation_id, number) replaces the
    -- old column constraint; SQLite treats UNIQUE as NULL-distinct, so
    -- multiple draft (number IS NULL) rows still never collide, same as
    -- before.
    CREATE TABLE quotes_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        organisation_id INTEGER,
        account_id INTEGER NOT NULL REFERENCES accounts(id),
        number TEXT,
        status TEXT NOT NULL,
        currency TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        expiry_date TEXT,
        created_at TEXT NOT NULL
    );
    INSERT INTO quotes_new (
        id, organisation_id, account_id, number, status, currency, issue_date, expiry_date, created_at
    )
    SELECT id, organisation_id, account_id, number, status, currency, issue_date, expiry_date, created_at
    FROM quotes;
    DROP TABLE quotes;
    ALTER TABLE quotes_new RENAME TO quotes;
    CREATE UNIQUE INDEX idx_quotes_organisation_number ON quotes (organisation_id, number);

    CREATE TABLE invoices_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        organisation_id INTEGER,
        account_id INTEGER NOT NULL REFERENCES accounts(id),
        quote_id INTEGER REFERENCES quotes(id),
        number TEXT,
        status TEXT NOT NULL,
        currency TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        due_date TEXT,
        created_at TEXT NOT NULL
    );
    INSERT INTO invoices_new (
        id, organisation_id, account_id, quote_id, number, status, currency, issue_date, due_date,
        created_at
    )
    SELECT id, organisation_id, account_id, quote_id, number, status, currency, issue_date, due_date,
        created_at
    FROM invoices;
    DROP TABLE invoices;
    ALTER TABLE invoices_new RENAME TO invoices;
    CREATE UNIQUE INDEX idx_invoices_organisation_number ON invoices (organisation_id, number);
    """,
    """
    -- Account addresses now follow the same UK GOV.UK Design System
    -- structure as BusinessProfile's (address_line1/address_line2/
    -- town_or_city/county/postcode) instead of one free-text field - see
    -- CLAUDE.md and data-model.md. address_line1 stays required (mirrors
    -- the old `address` NOT NULL column - an Account is a real client
    -- being billed, unlike BusinessProfile's fully-optional address);
    -- the rest are independently optional, same as BusinessProfile.
    -- Adding nullable columns, backfilling, and dropping the old one are
    -- all directly supported by SQLite's ALTER TABLE - no rebuild needed
    -- (see CLAUDE.md gotchas). The old free-text value moves into
    -- address_line1 wholesale, same as the historical business_profiles
    -- address split - a single string can't be reliably parsed into
    -- structured fields, so this doesn't guess at a split.
    ALTER TABLE accounts ADD COLUMN address_line1 TEXT NOT NULL DEFAULT '';
    ALTER TABLE accounts ADD COLUMN address_line2 TEXT;
    ALTER TABLE accounts ADD COLUMN town_or_city TEXT;
    ALTER TABLE accounts ADD COLUMN county TEXT;
    ALTER TABLE accounts ADD COLUMN postcode TEXT;
    UPDATE accounts SET address_line1 = address;
    ALTER TABLE accounts DROP COLUMN address;
    """,
    """
    -- Bank details (payment and tax settings group) and document
    -- header/footer (a new "document settings" group) - see
    -- CLAUDE.md/data-model.md and models.BusinessProfile's docstring. All
    -- five are nullable, no default: each is independently optional, same
    -- as utr/vat_number, and there's no sensible non-blank default for any
    -- of them. Plain ADD COLUMN, no rebuild needed.
    ALTER TABLE business_profiles ADD COLUMN bank_account_name TEXT;
    ALTER TABLE business_profiles ADD COLUMN bank_sort_code TEXT;
    ALTER TABLE business_profiles ADD COLUMN bank_account_number TEXT;
    ALTER TABLE business_profiles ADD COLUMN document_header TEXT;
    ALTER TABLE business_profiles ADD COLUMN document_footer TEXT;
    """,
]
