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
| POST | `/accounts` | required | Create an account (business_name, email, address required; contact_name, phone optional). |
| GET | `/accounts` | required | List all accounts. |
| GET | `/accounts/{id}` | required | Fetch one account. 404 if missing. |
| POST | `/quotes` | required | Create a draft quote (`account_id` required; `currency` defaults `USD`; `expiry_date` optional). |
| GET | `/quotes` | required | List quotes, optionally filtered by `?account_id=`. |
| GET | `/quotes/{id}` | required | Fetch one quote with its line items and total. |
| POST | `/quotes/{id}/line-items` | required | Add a line item to a draft quote. 409 if not draft. |
| POST | `/quotes/{id}/send` | required | Assign a quote number, transition `draft → sent`. 422 if no line items. |
| POST | `/quotes/{id}/convert` | required | Convert a `sent`/`accepted` quote into a new draft invoice, copying line items. 409 otherwise. |
| GET | `/quotes/{id}/pdf` | required | Render the quote as a PDF (`application/pdf`). |
| GET | `/invoices` | required | List invoices, optionally filtered by `?account_id=`. |
| GET | `/invoices/{id}` | required | Fetch one invoice with its line items and total. |
| POST | `/invoices/{id}/send` | required | Assign an invoice number and due date (issue date + the current user's `payment_terms_days`, default 30), transition `draft → sent`. 422 if no line items. |
| POST | `/invoices/{id}/void` | required | Transition to `void`. 409 if already `paid`. |
| GET | `/invoices/{id}/pdf` | required | Render the invoice as a PDF (`application/pdf`), with a "From" section for the current user's business name/address if set. |
| GET | `/settings/business-profile` | required | The current user's own profile. Never 404s — returns sensible defaults (`payment_terms_days: 30`, everything else blank/`null`) if nothing's been saved yet. |
| PUT | `/settings/business-profile` | required | Upsert it (`first_name`, `last_name`, `business_name`, `payment_terms_days` required; `title`, `address_line1`, `address_line2`, `town_or_city`, `county`, `postcode`, `utr`, `vat_number` optional — each address line independently optional). 422 on a blank required field or `payment_terms_days <= 0`. |

The CLI (`invoice-system-cli`) mirrors the account/quote/invoice routes
one-for-one over the same storage, but is **not** behind login — it's a
local, trusted tool (see `CLAUDE.md`). Where these routes resolve "which
user" from the Bearer token, the CLI takes an explicit `--user-id` instead:
`settings show`/`settings set` (no API equivalent by path, but the same
`BusinessProfileService` underneath), `invoice send --user-id`, `quote
pdf`/`invoice pdf --user-id`. Omit `--user-id` and those commands behave
exactly as if no profile existed (fixed 30-day due date, no "From" section).

## Conventions

- Money fields are JSON strings (`"unit_price": "129.99"`), never numbers —
  see `CLAUDE.md` conventions. A non-decimal string is rejected (422), not
  coerced.
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

## Not yet implemented

Payments, marking an invoice `paid`/`overdue`, and TOTP/2FA endpoints
(sessionkit supports it; no routes expose it yet) — see `docs/roadmap.md`.
