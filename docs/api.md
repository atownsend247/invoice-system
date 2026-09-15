# API

**Status: implemented** (`src/invoice_system/api/app.py`). Keep the
endpoint table in sync with the actual routes.

## Auth

**None yet.** Every route below is public — there is no login, session, or
per-account isolation. Don't rely on `account_id` in a request as a security
boundary; anyone can pass any id. See `CLAUDE.md` architecture rules.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Liveness check. |
| POST | `/accounts` | Create an account (business_name, email, address required; contact_name, phone optional). |
| GET | `/accounts` | List all accounts. |
| GET | `/accounts/{id}` | Fetch one account. 404 if missing. |
| POST | `/quotes` | Create a draft quote (`account_id` required; `currency` defaults `USD`; `expiry_date` optional). |
| GET | `/quotes` | List quotes, optionally filtered by `?account_id=`. |
| GET | `/quotes/{id}` | Fetch one quote with its line items and total. |
| POST | `/quotes/{id}/line-items` | Add a line item to a draft quote. 409 if not draft. |
| POST | `/quotes/{id}/send` | Assign a quote number, transition `draft → sent`. 422 if no line items. |
| POST | `/quotes/{id}/convert` | Convert a `sent`/`accepted` quote into a new draft invoice, copying line items. 409 otherwise. |
| GET | `/quotes/{id}/pdf` | Render the quote as a PDF (`application/pdf`). |
| GET | `/invoices` | List invoices, optionally filtered by `?account_id=`. |
| GET | `/invoices/{id}` | Fetch one invoice with its line items and total. |
| POST | `/invoices/{id}/send` | Assign an invoice number and due date (issue date + 30 days), transition `draft → sent`. 422 if no line items. |
| POST | `/invoices/{id}/void` | Transition to `void`. 409 if already `paid`. |
| GET | `/invoices/{id}/pdf` | Render the invoice as a PDF (`application/pdf`). |

The CLI (`invoice-system-cli`) mirrors this one-for-one over the same
storage — see `docs/development.md`.

## Conventions

- Money fields are JSON strings (`"unit_price": "129.99"`), never numbers —
  see `CLAUDE.md` conventions. A non-decimal string is rejected (422), not
  coerced.
- Timestamps (`created_at`) are ISO 8601 UTC strings; `issue_date`,
  `due_date`, `expiry_date` are plain `YYYY-MM-DD` dates.
- Errors map from the `core` exception hierarchy in one place
  (`handle_app_error` in `api/app.py`): `NotFound → 404`,
  `ValidationFailed → 422`, `Duplicate → 409`, `InvalidTransition → 409`.

## Not yet implemented

Accounts/sessions (login), payments, marking an invoice `paid`/`overdue`,
and the web client — see `docs/roadmap.md`.
