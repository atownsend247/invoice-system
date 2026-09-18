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
    """
    -- Every primary key in this schema (and every column that references
    -- one) switches from an autoincrementing INTEGER to an opaque UUID4
    -- TEXT string - matching sessionkit v0.2.0's own User.id change (see
    -- CLAUDE.md) and closing the same information leak: a sequential id in
    -- a URL/response reveals roughly how many rows exist and in what order
    -- they were created, which nothing should be able to infer about
    -- another organisation's activity (see data-model.md's Multi-tenancy).
    -- Ids are now generated in the application layer
    -- (OrganisationService/AccountService/QuoteService/InvoiceService/
    -- BusinessProfileService's injectable `IdGenerator`, see ids.py)
    -- before INSERT, not read back from `lastrowid` after.
    --
    -- This is a one-time authorized full reset, not a data-preserving
    -- migration: remapping every existing integer id to a UUID while
    -- rewriting every foreign key that points at it is possible but adds
    -- real complexity for no benefit on a pre-1.0 app with no production
    -- database to preserve (explicitly authorized by the user - see
    -- CLAUDE.md). Every table is dropped and recreated;
    -- `invoice-system-cli init-db` reseeds demo data with real UUIDs going
    -- forward. Don't reuse this "just drop everything" pattern for a
    -- future migration once real user data exists - that's exactly what
    -- forward-only, data-preserving migrations exist to avoid.
    --
    -- organisation_id on accounts/quotes/invoices is NOT NULL here, unlike
    -- migration 3 - that nullability existed only because ALTER TABLE ADD
    -- COLUMN can't add a NOT NULL column without a default; a fresh CREATE
    -- TABLE has no such restriction, and every row has always had one set
    -- at creation since Organisation was introduced.
    DROP TABLE IF EXISTS invoice_line_items;
    DROP TABLE IF EXISTS quote_line_items;
    DROP TABLE IF EXISTS invoices;
    DROP TABLE IF EXISTS quotes;
    DROP TABLE IF EXISTS accounts;
    DROP TABLE IF EXISTS business_profiles;
    DROP TABLE IF EXISTS organisation_members;
    DROP TABLE IF EXISTS organisations;
    DROP TABLE IF EXISTS counters;

    CREATE TABLE organisations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE organisation_members (
        organisation_id TEXT NOT NULL REFERENCES organisations(id),
        user_id TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        PRIMARY KEY (organisation_id, user_id)
    );

    CREATE TABLE accounts (
        id TEXT PRIMARY KEY,
        organisation_id TEXT NOT NULL REFERENCES organisations(id),
        business_name TEXT NOT NULL,
        contact_name TEXT,
        email TEXT NOT NULL,
        phone TEXT,
        address_line1 TEXT NOT NULL,
        address_line2 TEXT,
        town_or_city TEXT,
        county TEXT,
        postcode TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE quotes (
        id TEXT PRIMARY KEY,
        organisation_id TEXT NOT NULL REFERENCES organisations(id),
        account_id TEXT NOT NULL REFERENCES accounts(id),
        number TEXT,
        status TEXT NOT NULL,
        currency TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        expiry_date TEXT,
        created_at TEXT NOT NULL
    );
    CREATE UNIQUE INDEX idx_quotes_organisation_number ON quotes (organisation_id, number);

    CREATE TABLE quote_line_items (
        id TEXT PRIMARY KEY,
        quote_id TEXT NOT NULL REFERENCES quotes(id),
        description TEXT NOT NULL,
        quantity TEXT NOT NULL,
        unit_price TEXT NOT NULL,
        tax_rate TEXT NOT NULL DEFAULT '0',
        position INTEGER NOT NULL
    );

    CREATE TABLE invoices (
        id TEXT PRIMARY KEY,
        organisation_id TEXT NOT NULL REFERENCES organisations(id),
        account_id TEXT NOT NULL REFERENCES accounts(id),
        quote_id TEXT REFERENCES quotes(id),
        number TEXT,
        status TEXT NOT NULL,
        currency TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        due_date TEXT,
        created_at TEXT NOT NULL
    );
    CREATE UNIQUE INDEX idx_invoices_organisation_number ON invoices (organisation_id, number);

    CREATE TABLE invoice_line_items (
        id TEXT PRIMARY KEY,
        invoice_id TEXT NOT NULL REFERENCES invoices(id),
        description TEXT NOT NULL,
        quantity TEXT NOT NULL,
        unit_price TEXT NOT NULL,
        tax_rate TEXT NOT NULL DEFAULT '0',
        position INTEGER NOT NULL
    );

    CREATE TABLE counters (
        name TEXT PRIMARY KEY,
        value INTEGER NOT NULL
    );

    CREATE TABLE business_profiles (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL UNIQUE,
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
        bank_account_name TEXT,
        bank_sort_code TEXT,
        bank_account_number TEXT,
        document_header TEXT,
        document_footer TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    """
    -- Expenses - a cost incurred against an Account (see models.Expense).
    -- Unlike quotes/invoices there's no draft/sent status column: an
    -- expense is a record of money already spent, not a document with a
    -- lifecycle, so `number` is NOT NULL (assigned immediately at
    -- creation, never deferred to a later "send" step - see
    -- ExpenseService.create_expense) rather than nullable-until-sent like
    -- quotes.number/invoices.number. New tables, so a plain CREATE TABLE -
    -- no rebuild needed, same as every other addition in this file.
    CREATE TABLE expenses (
        id TEXT PRIMARY KEY,
        organisation_id TEXT NOT NULL REFERENCES organisations(id),
        account_id TEXT NOT NULL REFERENCES accounts(id),
        number TEXT NOT NULL,
        currency TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE UNIQUE INDEX idx_expenses_organisation_number ON expenses (organisation_id, number);

    CREATE TABLE expense_line_items (
        id TEXT PRIMARY KEY,
        expense_id TEXT NOT NULL REFERENCES expenses(id),
        description TEXT NOT NULL,
        quantity TEXT NOT NULL,
        unit_price TEXT NOT NULL,
        tax_rate TEXT NOT NULL DEFAULT '0',
        position INTEGER NOT NULL
    );
    """,
    """
    -- Expense attachments - supplementary PDFs (e.g. scanned receipts)
    -- uploaded against an Expense (see models.ExpenseAttachment,
    -- attachments.py's AttachmentStore). Metadata only: the bytes
    -- themselves live on disk, not in this database (see
    -- attachments.py's docstring for why) - `content_type`/`size` are
    -- still stored here purely for display/validation, same reasoning as
    -- LineItem's derived properties never being stored. No
    -- `organisation_id` column - same as expense_line_items, a caller
    -- always resolves tenant ownership via the parent `expense_id` first
    -- (ExpenseService.get_attachment_bytes/delete_attachment both call
    -- `_get_expense` before touching an attachment). New table, so a
    -- plain CREATE TABLE, no rebuild needed.
    CREATE TABLE expense_attachments (
        id TEXT PRIMARY KEY,
        expense_id TEXT NOT NULL REFERENCES expenses(id),
        filename TEXT NOT NULL,
        content_type TEXT NOT NULL,
        size INTEGER NOT NULL,
        created_at TEXT NOT NULL
    );
    """,
    """
    -- Indexes supporting server-side pagination/filtering of the
    -- accounts/quotes/invoices list pages (see sqlite_repository.py's
    -- list_accounts/list_quotes/list_invoices) - every one of those
    -- queries filters by organisation_id at minimum, and optionally by
    -- account_id/status too, and until now none of that had any index
    -- backing it (only the per-organisation number-uniqueness indexes
    -- existed). Plain CREATE INDEX statements, no rebuild needed, same as
    -- every other pure-addition migration in this file.
    CREATE INDEX idx_accounts_organisation ON accounts (organisation_id);
    CREATE INDEX idx_quotes_organisation_account ON quotes (organisation_id, account_id);
    CREATE INDEX idx_invoices_organisation_account ON invoices (organisation_id, account_id);
    CREATE INDEX idx_quotes_organisation_status ON quotes (organisation_id, status);
    CREATE INDEX idx_invoices_organisation_status ON invoices (organisation_id, status);
    """,
    """
    -- Registration invites - single-use, time-limited tokens gating the
    -- public /register page (see models.RegistrationInvite,
    -- RegistrationInviteService, api/auth.py's POST /auth/register). Not
    -- tied to an organisation_id or account_id - an invite exists before
    -- any Organisation does, and isn't scoped to one once consumed either
    -- (the resulting sessionkit user gets their own Organisation lazily on
    -- first login, same as every other user). `token` is the primary key
    -- (a UUID4, see ids.py) - nothing else ever looks one of these up.
    -- `used_at` is NULL until consumed. New table, so a plain CREATE
    -- TABLE, no rebuild needed, same as every other pure-addition
    -- migration in this file.
    CREATE TABLE registration_invites (
        token TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used_at TEXT
    );
    """,
    """
    -- business_profiles.document_header/document_footer split into three
    -- independent pairs, one per document type (quote/invoice/expense),
    -- so each can say something different - see models.BusinessProfile
    -- and pdf.py's quote_header_lines/quote_footer_lines and its
    -- invoice_/expense_ equivalents. Same shape as migration 5's
    -- accounts.address split: add the new nullable columns, copy the one
    -- old value into all three new header columns and all three new
    -- footer columns (existing users keep exactly what they had, just
    -- duplicated across the three - not dropped), then drop the old
    -- columns. All directly supported by SQLite's ALTER TABLE, no
    -- rebuild needed.
    ALTER TABLE business_profiles ADD COLUMN quote_document_header TEXT;
    ALTER TABLE business_profiles ADD COLUMN quote_document_footer TEXT;
    ALTER TABLE business_profiles ADD COLUMN invoice_document_header TEXT;
    ALTER TABLE business_profiles ADD COLUMN invoice_document_footer TEXT;
    ALTER TABLE business_profiles ADD COLUMN expense_document_header TEXT;
    ALTER TABLE business_profiles ADD COLUMN expense_document_footer TEXT;
    UPDATE business_profiles SET
        quote_document_header = document_header,
        invoice_document_header = document_header,
        expense_document_header = document_header,
        quote_document_footer = document_footer,
        invoice_document_footer = document_footer,
        expense_document_footer = document_footer;
    ALTER TABLE business_profiles DROP COLUMN document_header;
    ALTER TABLE business_profiles DROP COLUMN document_footer;
    """,
    """
    -- Backs list_invoices' new quote_id filter (find the invoice a given
    -- quote converted into - QuoteDetailPage.tsx's "View invoice" link on
    -- a converted quote) - same "index every filter column list_invoices/
    -- list_quotes/list_accounts actually use" pattern as migration 10's
    -- indexes. Plain CREATE INDEX, no rebuild needed.
    CREATE INDEX idx_invoices_organisation_quote ON invoices (organisation_id, quote_id);
    """,
    """
    -- A single brand accent colour ("#RRGGBB") used across every
    -- quote/invoice/expense PDF this user generates (see
    -- models.BusinessProfile's accent_color docstring and pdf.py) - one
    -- more nullable ADD COLUMN, no rebuild needed, same shape as every
    -- other pure-addition migration in this file.
    ALTER TABLE business_profiles ADD COLUMN accent_color TEXT;
    """,
    """
    -- Domains owned by an Account - which domain, when it expires, who
    -- it's registered with (see models.Domain). No organisation_id
    -- column - tenant ownership is resolved via the parent account first,
    -- same reasoning as expense_attachments not having one either. New
    -- table, so a plain CREATE TABLE + one CREATE INDEX on the foreign
    -- key it's actually queried by, no rebuild needed.
    CREATE TABLE domains (
        id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL REFERENCES accounts(id),
        domain_name TEXT NOT NULL,
        expiry_date TEXT NOT NULL,
        registrar TEXT NOT NULL,
        auto_renew INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX idx_domains_account ON domains (account_id);
    """,
]
