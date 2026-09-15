# API

**Status: planned, not yet implemented.** No routes exist yet. This is the
shape the first API scaffolding should implement — keep the endpoint table
in sync with the actual routes once `api/` exists.

## Auth

All routes below except `POST /accounts` (signup), `POST /sessions` (login),
and `GET /healthz` require an authenticated session, enforced at a single
dependency applied by default (see `CLAUDE.md` architecture rules).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Liveness check. Exempt from auth. |
| POST | `/accounts` | Create an account. Exempt from auth. |
| POST | `/sessions` | Log in. Exempt from auth. |
| GET | `/clients` | List the account's clients. |
| POST | `/clients` | Create a client. |
| GET | `/clients/{id}` | Fetch one client. |
| GET | `/invoices` | List invoices, filterable by `status`. |
| POST | `/invoices` | Create a draft invoice with line items. |
| GET | `/invoices/{id}` | Fetch one invoice with its line items and payments. |
| PATCH | `/invoices/{id}` | Edit a draft invoice (rejected once `sent`). |
| POST | `/invoices/{id}/send` | Transition `draft → sent`, assigns invoice number. |
| POST | `/invoices/{id}/payments` | Record a payment; may transition status to `paid`. |
| POST | `/invoices/{id}/void` | Transition to `void`. |

## Conventions

- Money fields are JSON strings (`"unit_price": "129.99"`), never numbers —
  see `CLAUDE.md` conventions. A float in the request body is rejected
  (422), not coerced.
- Timestamps are ISO 8601 UTC strings.
- Errors map from the `core` exception hierarchy: `NotFound → 404`,
  `ValidationFailed → 422`, `Duplicate → 409`, unauthenticated → `401`,
  unauthorized (someone else's account) → `403`. One place owns this
  mapping — see `architecture.md`.
