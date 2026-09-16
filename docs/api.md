# API

**Status: implemented** (`src/invoice_system/api/app.py`, `api/auth.py`).
Keep the endpoint table in sync with the actual routes.

## Auth

Login/sessions are [sessionkit](https://github.com/atownsend247/bb-py-sessionkit)
(see `CLAUDE.md`). Every route is behind a single `Authorization: Bearer
<token>` check (`domain_router`'s `dependencies=[Depends(get_current_user)]`
in `api/app.py`) except `GET /healthz` and `POST /auth/login`, which are
public. A missing/invalid/expired token gets `401`.

There is no signup route — create the first (and any further) login account
with the bundled `sessionkit` CLI: `uv run sessionkit add you@example.com`
(prompts for a password), against the file `INVOICE_SYSTEM_AUTH_DB` points
at (default `auth.db`).

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
| GET | `/auth/me` | required | The current user for this token. |
| POST | `/auth/logout` | required | Revoke the current token. `204`. |
| POST | `/accounts` | required | Create an account in the current user's organisation (business_name, email, address_line1 required; contact_name, phone, address_line2, town_or_city, county, postcode optional). |
| GET | `/accounts` | required | List accounts in the current user's organisation. |
| GET | `/accounts/{id}` | required | Fetch one account. 404 if missing *or* it belongs to a different organisation (see `docs/data-model.md`'s "Multi-tenancy"). |
| PUT | `/accounts/{id}` | required | Replace it (same required/optional fields as create — a full replace, not a partial patch). 404 if missing, 422 on a blank required field. |
| POST | `/quotes` | required | Create a draft quote (`account_id` required; `currency` defaults `USD`; `expiry_date` optional). |
| GET | `/quotes` | required | List quotes, optionally filtered by `?account_id=`. |
| GET | `/quotes/{id}` | required | Fetch one quote with its line items, `subtotal`, `tax_total`, and (gross) `total`. |
| POST | `/quotes/{id}/line-items` | required | Add a line item to a draft quote (`description`, `quantity`, `unit_price` required; `tax_rate` defaults `"0"`, must be within `[0, 1]`). 409 if not draft, 422 on an out-of-range `tax_rate`. |
| POST | `/quotes/{id}/send` | required | Assign a quote number, transition `draft → sent`. 422 if no line items. |
| POST | `/quotes/{id}/convert` | required | Convert a `sent`/`accepted` quote into a new draft invoice, copying line items. 409 otherwise. |
| GET | `/quotes/{id}/pdf` | required | Render the quote as a PDF (`application/pdf`) - the web UI offers this both as a download and as an in-page preview (see Conventions below), the route itself is the same either way. |
| GET | `/invoices` | required | List invoices, optionally filtered by `?account_id=`. |
| GET | `/invoices/{id}` | required | Fetch one invoice with its line items, `subtotal`, `tax_total`, and (gross) `total`. |
| POST | `/invoices/{id}/send` | required | Assign an invoice number and due date (issue date + the current user's `payment_terms_days`, default 30), transition `draft → sent`. 422 if no line items. |
| POST | `/invoices/{id}/void` | required | Transition to `void`. 409 if already `paid`. |
| POST | `/invoices/{id}/pay` | required | Transition `sent → paid`. 409 if not currently `sent` (covers `draft`, `void`, and already-`paid`). |
| GET | `/invoices/monthly-totals` | required | Registered *before* `/invoices/{id}` (see `CLAUDE.md`'s architecture rules on route ordering). `{currency, months: [{month, paid_total, unpaid_total}]}` for the trailing 12 months, scoped to the current user's organisation, in the current user's business profile `currency`. An invoice in any other currency isn't counted. |
| GET | `/invoices/{id}/pdf` | required | Render the invoice as a PDF (`application/pdf`), with a "From" section for the current user's business name/address if set, and their `document_header`/`document_footer` (if set) above the title/below the totals table. |
| POST | `/expenses` | required | Create an expense against an account (`account_id` required; `currency` defaults `USD`). Unlike a quote, its `EXP-0001` `number` is assigned immediately - there's no draft state (see `CLAUDE.md`). |
| GET | `/expenses` | required | List expenses, optionally filtered by `?account_id=`. |
| GET | `/expenses/{id}` | required | Fetch one expense with its line items, `subtotal`, `tax_total`, and (gross) `total`. |
| POST | `/expenses/{id}/line-items` | required | Add a line item (`description`, `quantity`, `unit_price` required; `tax_rate` defaults `"0"`, must be within `[0, 1]`) - not gated behind any status check, unlike `POST /quotes/{id}/line-items` (there's no draft/sent distinction to gate on). 422 on an out-of-range `tax_rate`. |
| GET | `/expenses/{id}/pdf` | required | Render the expense as a PDF (`application/pdf`), same "View PDF"/"Download PDF" pattern as quotes/invoices - but with no "Status:" line and no due/expiry date, since an expense has neither. |
| GET | `/settings/business-profile` | required | The current user's own profile. Never 404s — returns sensible defaults (`payment_terms_days: 30`, `currency: "GBP"`, everything else blank/`null`) if nothing's been saved yet. |
| PUT | `/settings/business-profile` | required | Upsert it (`first_name`, `last_name`, `business_name`, `payment_terms_days` required; `currency` defaults `"GBP"`; `title`, `address_line1`, `address_line2`, `town_or_city`, `county`, `postcode`, `utr`, `vat_number`, `bank_account_name`, `bank_sort_code`, `bank_account_number`, `document_header`, `document_footer` optional — each address line independently optional). 422 on a blank required field, `payment_terms_days <= 0`, or a blank `currency`. |
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
list/send/void/pay/monthly-totals/pdf`, `expense create/list/add-item/pdf`,
`stats`) purely to resolve
`organisation_id` (`OrganisationService.get_or_create_for_user`, same
auto-create-on-first-use as the API) — this is a breaking change from
before `Organisation` existed, when these commands took no user context at
all. `quote pdf`/`invoice pdf`/`expense pdf --user-id` and `invoice send
--user-id` also
reuse that same user id for their pre-existing purpose (the PDF "From"
section, the payment-terms-driven due date) — `settings show`/`settings
set --user-id` (no API equivalent by path, but the same
`BusinessProfileService` underneath) are unaffected, since `BusinessProfile`
stays per-user, not per-organisation (see `docs/data-model.md`'s
"Multi-tenancy"). `init-db` has no API equivalent at all (there's no `POST
/accounts/db` — bootstrapping is CLI-only) and seeds demo data by default;
`--no-demo` skips it. See `docs/data-model.md`'s "Demo data" section and
`CLAUDE.md`.

## Conventions

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
