# API

**Status: implemented** (`src/invoice_system/api/app.py`, `api/auth.py`).
Keep the endpoint table in sync with the actual routes.

## Auth

Login/sessions are [sessionkit](https://github.com/atownsend247/bb-py-sessionkit)
(see `CLAUDE.md`). Every route is behind a single `Authorization: Bearer
<token>` check (`domain_router`'s `dependencies=[Depends(get_current_user)]`
in `api/app.py`) except `GET /healthz`, `POST /auth/login`, `GET
/auth/register/validate`, and `POST /auth/register`, which are public. A
missing/invalid/expired token gets `401`.

There is no *unconditional* signup route — the normal way to create a login
is still the bundled `sessionkit` CLI: `uv run sessionkit add
you@example.com` (prompts for a password), against the file
`INVOICE_SYSTEM_AUTH_DB` points at (default `storage/db/auth.db` — see
`docs/development.md`'s "Where persistent data lives"). `POST
/auth/register` is a narrow, invite-gated exception: it only works with a
valid `RegistrationInvite` token (single-use, expires after 7 days by
default), which itself can **only** be created via `invoice-system-cli
invite create [--expires-in-days N]` — there is deliberately no API route
to create one. See the Conventions section below for the full flow.

## CORS

`CORSMiddleware` allows every origin by default (`INVOICE_SYSTEM_CORS_ORIGINS`
to restrict it — comma-separated) — see `CLAUDE.md` for why that's an
acceptable default for a Bearer-token API. Needed so `web/` (a different
port in dev, and likely a different origin in prod) can call this API at all.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/healthz` | public | Liveness check. |
| POST | `/auth/login` | public | `{email, password, otp?}` → `{token, expires_at, user}`. `401` on bad credentials or a missing/invalid TOTP code. |
| GET | `/auth/register/validate` | public | `?token=` → `{valid: true}`, or `404` if the token is unknown, expired, or already used (indistinguishable, deliberately). Lets the web UI show an error on page load rather than only at submit time. |
| POST | `/auth/register` | public | `{token, email, password}` → the created user (same shape as `/auth/login`'s `user`), `201`. Consumes the invite *before* creating the login, so a `409` (duplicate email) or `422` (e.g. password under 8 characters) still burns it — see Conventions below. `404` for the same three invite-invalid cases as the validate route above. |
| GET | `/auth/me` | required | The current user for this token. |
| POST | `/auth/logout` | required | Revoke the current token. `204`. |
| POST | `/accounts` | required | Create an account in the current user's organisation (business_name, email, address_line1 required; contact_name, phone, address_line2, town_or_city, county, postcode optional). |
| GET | `/accounts` | required | Paginated list of accounts in the current user's organisation - `{items, total}`. `?query=` matches (case-insensitively) business/contact name, email, phone, or any set address line. `?page=`/`?page_size=` (defaults `1`/`20`, `page_size` max `200`) - see Conventions below. |
| GET | `/accounts/{id}` | required | Fetch one account. 404 if missing *or* it belongs to a different organisation (see `docs/data-model.md`'s "Multi-tenancy"). |
| PUT | `/accounts/{id}` | required | Replace it (same required/optional fields as create — a full replace, not a partial patch). 404 if missing, 422 on a blank required field. |
| POST | `/accounts/{id}/domains` | required | Add a domain to this account (`domain_name`, `expiry_date`, `registrar` required; `auto_renew` optional, defaults `false`). 404 if the account is missing/wrong organisation, 422 on a blank `domain_name`/`registrar`. |
| GET | `/accounts/{id}/domains` | required | List this account's domains, soonest-expiry-first (not the newest-first convention every other list here uses) - a plain array, not paginated (see Conventions below). No single-domain `GET` route - the list is the only read path. |
| PUT | `/accounts/{id}/domains/{domain_id}` | required | Replace a domain (same fields as create - a full replace). 404 if missing/wrong account, 422 on a blank `domain_name`/`registrar`. |
| DELETE | `/accounts/{id}/domains/{domain_id}` | required | Delete it. 204, 404 if missing/wrong account. |
| POST | `/registrars` | required | Add a registrar to the current user's organisation (`name` required; `notes` optional). 422 on a blank `name`. |
| GET | `/registrars` | required | List the organisation's registrars, alphabetically by name (not the newest-first convention most lists here use) - a plain array, not paginated (see Conventions below). Populates the Domain form's registrar `<select>`. |
| PUT | `/registrars/{id}` | required | Replace a registrar (same fields as create - a full replace). 404 if missing/wrong organisation, 422 on a blank `name`. |
| DELETE | `/registrars/{id}` | required | Delete it. 204, 404 if missing/wrong organisation. Safe with no cascade - `Domain.registrar` stores the chosen name as a plain string, not a reference to this row (see Conventions below). |
| POST | `/quotes` | required | Create a draft quote (`account_id` required; `currency` defaults `USD`; `issue_date` optional, defaults to today). `expiry_date` is computed server-side as `issue_date + ` the caller's `BusinessProfile.quote_validity_days` - not a request field. |
| GET | `/quotes` | required | Paginated list of quotes - `{items, total}`. Optionally filtered by `?account_id=` (exact), `?account_name=` (matches the linked account's business_name, case-insensitively), and/or `?status=` (`draft`/`sent`/`accepted`/`rejected`/`expired`/`converted`). `?page=`/`?page_size=`, same as `/accounts` - see Conventions below. |
| GET | `/quotes/{id}` | required | Fetch one quote with its line items, `events` (its audit trail, newest-first - see Conventions below), `subtotal`, `tax_total`, and (gross) `total`. |
| POST | `/quotes/{id}/line-items` | required | Add a line item to a draft quote (`description`, `quantity`, `unit_price` required; `tax_rate` defaults `"0"`, must be within `[0, 1]`). 409 if not draft, 422 on an out-of-range `tax_rate`. |
| POST | `/quotes/{id}/send` | required | Assign a quote number (using the caller's own `quote_number_prefix`/`quote_number_digits`, e.g. `Q-0001` by default - see Conventions below), transition `draft → sent`. 422 if no line items. |
| POST | `/quotes/next-number` | required | `{next_number}` - jump the organisation's quote counter so the *next* quote sent gets exactly this number, regardless of how many quotes already exist (see Conventions below). `204`, `422` if `next_number < 1`. |
| POST | `/quotes/{id}/convert` | required | Convert a `sent`/`accepted` quote into a new draft invoice, copying line items (`issue_date` optional in the request body, defaults to today - lets the caller backdate the resulting invoice). 409 otherwise. |
| GET | `/quotes/{id}/pdf` | required | Render the quote as a PDF (`application/pdf`) - the web UI offers this both as a download and as an in-page preview (see Conventions below), the route itself is the same either way. |
| GET | `/invoices` | required | Paginated list of invoices - `{items, total}`. Optionally filtered by `?account_id=` (exact), `?account_name=` (matches the linked account's business_name, case-insensitively), `?status=` (`draft`/`sent`/`paid`/`void` - `overdue` is accepted but never matches anything, see Conventions below), and/or `?quote_id=` (exact - a quote converts to at most one invoice, so this matches 0 or 1 row; used by `QuoteDetailPage.tsx`'s "View invoice" button on a converted quote). `?page=`/`?page_size=`, same as `/accounts`. |
| GET | `/invoices/{id}` | required | Fetch one invoice with its line items, `events` (its audit trail, newest-first - see Conventions below), `subtotal`, `tax_total`, and (gross) `total`. |
| POST | `/invoices/{id}/send` | required | Assign an invoice number (using the caller's own `invoice_number_prefix`/`invoice_number_digits`, e.g. `INV-0001` by default) and due date (`issue_date` + the current user's `payment_terms_days`, default 30 - not "today", so a backdated invoice's due date reflects when it was actually issued), transition `draft → sent`. 422 if no line items. |
| POST | `/invoices/next-number` | required | `{next_number}` - jump the organisation's invoice counter so the *next* invoice sent gets exactly this number (see Conventions below). `204`, `422` if `next_number < 1`. |
| POST | `/invoices/{id}/void` | required | Transition to `void`. 409 if already `paid`. |
| POST | `/invoices/{id}/pay` | required | Transition `sent → paid`. 409 if not currently `sent` (covers `draft`, `void`, and already-`paid`). |
| GET | `/invoices/monthly-totals` | required | Registered *before* `/invoices/{id}` (see `CLAUDE.md`'s architecture rules on route ordering). `{currency, months: [{month, paid_total, unpaid_total}]}` for the trailing 12 months, scoped to the current user's organisation, in the current user's business profile `currency`. An invoice in any other currency isn't counted. |
| GET | `/invoices/{id}/pdf` | required | Render the invoice as a PDF (`application/pdf`), with a "From" section for the current user's business name/address if set (with "Bill to" beside it, not below, when it is), their `invoice_document_header`/`invoice_document_footer` (if set) above the title/below the totals table, and — invoices only, never quotes or expenses — a "Payment details" section for whichever of `bank_account_name`/`bank_sort_code`/`bank_account_number` are set, after the totals table. Quotes/expenses render the same way via their own `quote_document_header`/`quote_document_footer`/`expense_document_header`/`expense_document_footer` pair instead - see the Conventions section. |
| POST | `/expenses` | required | Create an expense against an account (`account_id` required; `currency` defaults `USD`; `expense_date` optional, defaults to today). Unlike a quote, its `number` (using the caller's own `expense_number_prefix`/`expense_number_digits`, e.g. `EXP-0001` by default) is assigned immediately - there's no draft state (see `CLAUDE.md`). |
| POST | `/expenses/next-number` | required | `{next_number}` - jump the organisation's expense counter so the *next* expense created gets exactly this number (see Conventions below). `204`, `422` if `next_number < 1`. |
| GET | `/expenses` | required | List expenses, optionally filtered by `?account_id=`. |
| GET | `/expenses/{id}` | required | Fetch one expense with its line items, `subtotal`, `tax_total`, and (gross) `total`. |
| PUT | `/expenses/{id}/expense-date` | required | Update just `expense_date` (required) - the one `Expense` field editable after creation, unlike `account_id`/`currency`/`issue_date`. 404 if missing/wrong organisation. |
| POST | `/expenses/{id}/line-items` | required | Add a line item (`description`, `quantity`, `unit_price` required; `tax_rate` defaults `"0"`, must be within `[0, 1]`) - not gated behind any status check, unlike `POST /quotes/{id}/line-items` (there's no draft/sent distinction to gate on). 422 on an out-of-range `tax_rate`. |
| PUT | `/expenses/{id}/line-items/{item_id}` | required | Replace a line item's `description`/`quantity`/`unit_price`/`tax_rate` (same body/validation as create) - unlike `Quote`/`Invoice`, an `Expense`'s line items are editable, not frozen. 404 if the expense or the item doesn't resolve under the caller's organisation, 422 on an out-of-range `tax_rate`. |
| DELETE | `/expenses/{id}/line-items/{item_id}` | required | Remove a line item. Returns the updated `ExpenseOut` (`200`, not `204`) so the caller gets recomputed totals without a second request. 404 if the expense or the item doesn't resolve under the caller's organisation. |
| GET | `/expenses/{id}/pdf` | required | Render the expense as a PDF (`application/pdf`), same "View PDF"/"Download PDF" pattern as quotes/invoices - but with no "Status:" line and no due/expiry date, since an expense has neither. |
| GET | `/expenses/monthly-totals` | required | Registered *before* `/expenses/{id}` (same route-ordering reasoning as `/invoices/monthly-totals`). `{currency, months: [{month, total}]}` for the trailing 12 months, scoped to the current user's organisation, in the current user's business profile `currency`. Bucketed by `expense_date` (when the money was actually spent), **not** `issue_date` (when it was recorded) - see Conventions below. Same aggregation as `/invoices/monthly-totals` but with no paid/unpaid split - an expense has no status. The web UI's home-dashboard chart renders this as a third (red) bar series alongside Paid/Outstanding. |
| POST | `/expenses/{id}/attachments` | required | Upload a supplementary PDF (e.g. a scanned receipt) against an expense - `multipart/form-data`, one `file` field. Content-Type must be `application/pdf` or the filename must end `.pdf`; max 10MB (`core.py`'s `MAX_ATTACHMENT_SIZE`). 422 on anything else. Addable at any time - no status to gate on, same as line items. |
| GET | `/expenses/{id}/attachments/{attachment_id}` | required | The uploaded bytes (`Content-Type` is whatever was uploaded, `Content-Disposition: inline` - the web UI's "View"/"Download" both hit this one route, same pattern as the generated PDF routes above). |
| DELETE | `/expenses/{id}/attachments/{attachment_id}` | required | Delete it. `204`. |
| GET | `/settings/business-profile` | required | The current user's own profile. Never 404s — returns sensible defaults (`payment_terms_days: 30`, `quote_validity_days: 30`, `currency: "GBP"`, everything else blank/`null`) if nothing's been saved yet. |
| PUT | `/settings/business-profile` | required | Upsert it. `payment_terms_days`, `quote_validity_days`, `quote_number_prefix`, `quote_number_digits`, `invoice_number_prefix`, `invoice_number_digits`, `expense_number_prefix`, `expense_number_digits`, and `currency` all have schema defaults (`30`, `30`, `"Q-"`, `4`, `"INV-"`, `4`, `"EXP-"`, `4`, `"GBP"`) but are still validated once resolved (see below) - the request body can omit any of them. `first_name`, `last_name`, `business_name` also default to `""` when omitted and are **not** validated for non-blankness at all - see Conventions below for why. `title`, `address_line1`, `address_line2`, `town_or_city`, `county`, `postcode`, `utr`, `vat_number`, `bank_account_name`, `bank_sort_code`, `bank_account_number`, `quote_document_header`, `quote_document_footer`, `invoice_document_header`, `invoice_document_footer`, `expense_document_header`, `expense_document_footer`, `accent_color` are all optional too — each address line independently optional, each document header/footer is its own independent pair per document type, not one shared pair, and `accent_color` (a `#RRGGBB` hex string, one shared value across all three document types) is the one field here whose format is actually validated, not accepted as free-form text - see the Conventions section. 422 on `payment_terms_days <= 0`, `quote_validity_days <= 0`, any `*_number_digits < 1`, a blank `currency`, or a malformed `accent_color`. |
| GET | `/stats` | required | All-time counters for the home dashboard, scoped to the current user's organisation: `{account_count, quote_count, invoice_count, quotes_sent_count, quotes_converted_count, total_paid, currency}`. `total_paid` is filtered to `currency` (the caller's own business profile's reporting currency, same resolution as `/invoices/monthly-totals`) — a paid invoice in a different currency isn't counted. `quotes_sent_count`/`quotes_converted_count` are raw counts, not a precomputed rate; the web UI derives a conversion percentage from them client-side (`HomePage.tsx`'s `conversionRate`). |

Every account/quote/invoice/expense route above resolves the caller's
`organisation_id` server-side (`api/app.py`'s `get_organisation_id`
dependency: `Bearer token → user → application.organisations.get_or_create_for_user(user.id)`,
auto-creating an `Organisation` on a user's first domain request) — it is
never sent or returned in a request/response body. See
`docs/data-model.md`'s "Multi-tenancy" section.

The CLI (`invoice-system-cli`) mirrors the account/quote/invoice/expense
routes
one-for-one over the same storage, but is **not** behind login — it's a
local, trusted tool (see `CLAUDE.md`). Where the API resolves both "which
user" and "which organisation" from the Bearer token, the CLI has no
session to resolve either from, so **every** `account`/`quote`/`invoice`/
`expense`
command takes a **required** `--user-id` (`account create/list/update`,
`quote create/add-item/send/convert/pdf`, `invoice
list/send/void/pay/monthly-totals/pdf`, `expense
create/list/add-item/update-item/delete-item/monthly-totals/pdf`,
`expense attachment add/list/download/delete`,
`stats`) purely to resolve
`organisation_id` (`OrganisationService.get_or_create_for_user`, same
auto-create-on-first-use as the API) — this is a breaking change from
before `Organisation` existed, when these commands took no user context at
all. `account list`/`invoice list` additionally take `--page`/`--page-size`
(default `1`/`100`) mirroring the API's own pagination, printing a
trailing `Page X of Y (total N)` line - there is no `quote list` command
at all, so quotes have nothing to paginate on the CLI side.
`expense add-item` echoes the new line item's id (`Added line item
<id>`) - the only `add-*` command that does, since `expense update-item`/
`expense delete-item <expense_id> <item_id>` need it and there's no
`expense get`/`show` command to look it up afterward otherwise.
`quote pdf`/`invoice pdf`/`expense pdf --user-id` and `invoice send
--user-id` also
reuse that same user id for their pre-existing purpose (the PDF "From"
section, the payment-terms-driven due date) - `quote create --user-id` does
too, resolving `quote_validity_days` the same way; `quote send`/`invoice
send`/`expense create --user-id` additionally resolve that profile's
`quote_number_prefix`/`quote_number_digits` (etc.) to format the assigned
number - see the number-prefix/digits Convention above. `quote create`/`quote
convert` both additionally take an optional `--issue-date` (`YYYY-MM-DD`,
defaults to today - see the issue-date-driven dates Convention below).
`settings show`/`settings
set --user-id` (no API equivalent by path, but the same
`BusinessProfileService` underneath) are unaffected, since `BusinessProfile`
stays per-user, not per-organisation (see `docs/data-model.md`'s
"Multi-tenancy"); `settings set` gains `--quote-number-prefix`/
`--quote-number-digits`/`--invoice-number-prefix`/`--invoice-number-digits`/
`--expense-number-prefix`/`--expense-number-digits`, mirrored by three new
`--user-id`-scoped commands with no API equivalent by path (same
`set_next_number` service methods the `next-number` routes above call) -
`quote set-next-number --next-number N`, `invoice set-next-number
--next-number N`, `expense set-next-number --next-number N`. `init-db` has
no API equivalent at all (there's no `POST
/accounts/db` — bootstrapping is CLI-only) and seeds demo data by default;
`--no-demo` skips it. `init-db --reset` deletes all existing domain data
and uploaded expense attachments before reinitialising - irreversible, so
it prompts for confirmation unless `--yes`/`-y` is also given; it
deliberately leaves `auth.db` (login users) untouched - see CLAUDE.md's
`init-db --reset` gotcha for why that needed a small `seed_demo_data` fix.
See `docs/data-model.md`'s "Demo data" section and `CLAUDE.md`.

## Conventions

- **Audit trail**: every quote/invoice's `events` field is its history of
  creation and status changes only (not every field edit), newest-first -
  `{id, event_type: "created" | "status_changed", from_status, to_status,
  occurred_at}`, `from_status` is `null` for a `created` event. Recorded
  automatically by every status-changing route above (`POST /quotes`,
  `/send`, `/convert`, `POST /invoices/{id}/send|void|pay`) - there's no
  separate route to read or write it, it's just part of
  `QuoteOut`/`InvoiceOut`.
- **Issue-date-driven dates**: `POST /quotes`' `issue_date` (defaults to
  today) is what `expiry_date` is calculated from
  (`issue_date + BusinessProfile.quote_validity_days`), and `POST
  /quotes/{id}/convert`'s `issue_date` (also defaults to today, but lets
  the caller *backdate* the resulting invoice) is in turn what `POST
  /invoices/{id}/send`'s `due_date` is calculated from
  (`issue_date + payment_terms_days`) - not "today" in either case. An
  `Invoice.issue_date` can only ever be set at conversion time, since
  there's no standalone "create invoice" route.
- **Per-document-type header/footer**: `quote_document_header`/
  `quote_document_footer`, `invoice_document_header`/
  `invoice_document_footer`, and `expense_document_header`/
  `expense_document_footer` are three independent pairs, not one shared
  pair - a quote/invoice/expense PDF only ever shows its own pair, never
  another type's. All six are free text, each independently optional,
  each split into non-blank lines when rendered.
- **`first_name`/`last_name`/`business_name` are not required to be
  non-blank**, unlike every other field this route validates - they're
  the only three `BusinessProfile` fields with no sensible default to
  fall back to (`payment_terms_days`/`quote_validity_days`/`currency`/the
  number-prefix/digits fields below all have one). The settings page
  presents these four groups as tabs sharing **one** `PUT` (see
  `CLAUDE.md`'s settings-page tabs Convention) - requiring them non-blank
  meant a user filling in just one tab before ever touching User/Business
  couldn't save anything at all, since the shared request always carries
  every field along. A blank value is accepted and stored as `""`, not
  normalised to `null` (unlike `title`/address lines/`utr`/etc.) - these
  stay a plain string field, since nothing reads them as "never set" vs.
  "set to blank" (`pdf.py`'s `business_profile_lines()` already just
  checks non-blank either way, and neither is ever shown on a PDF at all
  for `first_name`/`last_name`).
- **Document number prefix/digits and "set next number"**:
  `quote_number_prefix`/`quote_number_digits` (default `"Q-"`/`4`),
  `invoice_number_prefix`/`invoice_number_digits` (default `"INV-"`/`4`),
  and `expense_number_prefix`/`expense_number_digits` (default `"EXP-"`/`4`)
  control how each document type's number is formatted
  (`f"{prefix}{value:0{digits}d}"`) when it's assigned - `POST
  /quotes/{id}/send`/`POST /invoices/{id}/send`/`POST /expenses` read
  these from the caller's own business profile at the moment a number is
  assigned, so changing them only affects numbers issued from then on,
  never rewrites an already-issued one. `POST /quotes|invoices|expenses/
  next-number` is a separate, one-time **jump**, not a persisted additive
  offset — `{next_number: 67}` sets the counter so the very next document
  of that type is exactly `67`, regardless of how many already exist
  (an additive offset would instead land on `existing_count + 67`).
- **`accent_color`**: one shared `#RRGGBB` hex colour, used as the brand
  colour across every quote/invoice/expense PDF (unlike the header/footer
  pairs above, not per-document-type). The one `business-profile` field
  whose format is actually validated (`^#[0-9a-fA-F]{6}$`, 422 otherwise)
  rather than accepted as free text — it's interpolated directly into a
  CSS declaration in the rendered PDF template, not shown as escaped body
  text. Falls back to a fixed neutral constant when unset.
- **`Domain`**: which domains an account owns, when each expires, who it's
  registered with, and whether it's set to auto-renew - see the routes
  table above. Always accessed through its parent account
  (`/accounts/{id}/domains...`), not a standalone `/domains` collection -
  404s the same way a mismatched-organisation account does if `{id}`
  doesn't resolve under the caller's own organisation. `domain_name`/
  `expiry_date`/`registrar` are all required; no format validation on
  `domain_name` beyond non-blank, same as `Account.email`/`business_name`.
  Editable in place (`PUT`), not add-only - a domain's expiry changes on
  every renewal and its registrar can change on a transfer.
- **`Registrar`**: a business's managed list of domain registrars, used to
  populate the Domain form's registrar `<select>` (strictly select-from-
  list, no free-text option). Top-level (`/registrars`), not nested under
  `/accounts` like `Domain` - a registrar has no parent, it's
  organisation-wide. `name` required, `notes` optional free text (e.g. a
  support URL). Editable in place and deletable - unlike `Account`,
  deleting a `Registrar` has no cascade to worry about, since
  `Domain.registrar` stores the chosen name as a plain string rather than
  referencing this row's id (renaming or deleting a registrar later never
  needs to touch domains that already recorded its name).
- **`Expense.issue_date` vs `expense_date`**: `issue_date` is when the
  record was created (a system timestamp, never editable); `expense_date`
  is when the money was actually spent (defaults to today at creation,
  the one `Expense` field editable afterward via `PUT
  /expenses/{id}/expense-date`). `GET /expenses/monthly-totals` buckets by
  `expense_date`, so a backdated entry (e.g. logging a receipt for
  something bought last week) lands in the month it actually happened,
  not the month it was typed in.
- **Invite-gated registration**: `invoice-system-cli invite create
  [--expires-in-days N]` (default 7) creates a single-use
  `RegistrationInvite` and prints its token plus a relative `/register?
  token=...` link — there's no API route to create one, only to check/
  consume it. `RegistrationInviteService.check_invite`/`consume_invite`
  (`core.py`) treat an unknown, expired, and already-used token
  identically (`NotFound` → `404`), so neither `GET /auth/register/
  validate` nor `POST /auth/register` ever reveal which of the three
  applies. `POST /auth/register` consumes the invite *before* calling
  `sessionkit.AuthService.create_user` — if that then fails (`409`
  duplicate email, `422` invalid email/password-too-short), the invite is
  burned but two concurrent submissions of the same token can never both
  succeed. Registration does **not** auto-login (no token in the
  response) and doesn't touch `Organisation`/`BusinessProfile` at all —
  the new user gets their own `Organisation` lazily on first login, same
  as every other user.
- `GET /accounts`/`GET /quotes`/`GET /invoices` are the only paginated
  endpoints (`GET /expenses`, `GET /accounts/{id}/domains`, and `GET
  /registrars` all stay a bare array - none has a standalone list page of
  its own, and each is inherently small: one client's own domain count,
  or one business's own registrar list - see the `Domain`/`Registrar`
  bullets below). Response shape is `{items: [...], total}`,
  not a bare array - `total` is the count matching the request's filters
  across *every* page, letting the client compute how many pages exist
  without a second request. `page` defaults to `1`, `page_size` to `20`
  (max `200` - `422` outside `[1, 200]`, same for `page < 1`). Filtering
  and pagination compose: a filter narrows what gets paginated, it doesn't
  run client-side over an unfiltered page. `AccountDetailPage.tsx`'s own
  `?account_id=`-scoped fetches (one client's full quote/invoice history)
  request `page_size=200` explicitly rather than relying on the default,
  since that's inherently bounded by one client relationship, not
  organisation-wide growth, and 200 is comfortably above any realistic
  single account's history.
- Money fields are JSON strings (`"unit_price": "129.99"`), never numbers —
  see `CLAUDE.md` conventions. A non-decimal string is rejected (422), not
  coerced. `tax_rate` is the same convention (a decimal-string fraction,
  e.g. `"0.20"`), not a number 0-100.
- Timestamps (`created_at`) are ISO 8601 UTC strings; `issue_date`,
  `due_date`, `expiry_date` are plain `YYYY-MM-DD` dates.
- Errors map from two exception hierarchies, each in its own handler in
  `api/app.py`: this app's own (`handle_app_error`) — `NotFound → 404`,
  `ValidationFailed → 422`, `Duplicate → 409`, `InvalidTransition → 409` —
  and sessionkit's `AuthError` (`handle_auth_error`) — `AuthenticationError
  → 401` (covers `OtpRequired`/`OtpLocked`), `UserNotFound → 404`,
  `DuplicateUser → 409`, `ValidationError → 422`. `OtpInvalid` is `422`
  everywhere except `POST /auth/login`, where the route maps it to `401`
  itself (see `api/auth.py`) since a bad TOTP code at login is
  indistinguishable from bad credentials to the caller.
- `GET /quotes/{id}/pdf`/`GET /invoices/{id}/pdf`/`GET /expenses/{id}/pdf`
  are a single route each,
  not one per "view" vs "download" - that distinction is purely a web UI
  concern (`web/src/pages/QuoteDetailPage.tsx`/`InvoiceDetailPage.tsx`/
  `ExpenseDetailPage.tsx`
  offer both as separate buttons over the same response bytes: "Download
  PDF" forces a browser download, "View PDF" shows an in-page preview via
  `components/PdfViewerModal.tsx` - **not** a new browser tab, see
  `CLAUDE.md`'s conventions for why that doesn't work against modern
  Chromium's `blob:` URL restrictions). No new route, no query param.

## Not yet implemented

Partial-payment tracking (a `Payment` model/ledger), a real `sent → overdue`
status transition, and TOTP/2FA endpoints (sessionkit supports it; no routes
expose it yet) — see `docs/roadmap.md`. Marking an invoice fully `paid` (`POST
/invoices/{id}/pay`) is implemented.
