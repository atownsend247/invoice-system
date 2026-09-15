# Data model

**Status: planned, not yet implemented.** This is the model the first
migration should create. Keep this table in sync with the actual schema
once `storage/` exists — this doc is read as ground truth.

## Entities

| Entity | Key fields | Notes |
|---|---|---|
| `Account` | id, email, password_hash, created_at | Owns everything below. Cross-cutting (`accounts.py`), not domain. |
| `Client` | id, account_id, name, email, billing_address | Belongs to one account. |
| `Invoice` | id, account_id, client_id, number, status, currency, issue_date, due_date, created_at | `status`: `draft \| sent \| paid \| overdue \| void`. `number` is unique per account, generated not user-supplied. |
| `LineItem` | id, invoice_id, description, quantity, unit_price, position | `unit_price` is `Decimal`; line total is derived (`quantity * unit_price`), never stored redundantly. |
| `Payment` | id, invoice_id, amount, paid_at, method | An invoice can have multiple partial payments; `status` moves to `paid` once the sum of payments meets the invoice total. |

## Relationships

```
Account 1──* Client
Account 1──* Invoice
Client  1──* Invoice
Invoice 1──* LineItem
Invoice 1──* Payment
```

## Invariants enforced in `core`, not in storage

- `LineItem`s are immutable once their `Invoice.status` leaves `draft`
  (issue a correction/credit note instead of editing history — see
  `CLAUDE.md` conventions).
- `Invoice.number` is assigned by the service on transition out of `draft`,
  not on creation — a draft can be deleted without leaving a gap.
- Money fields (`unit_price`, `Payment.amount`) are `Decimal` end-to-end;
  the storage layer stores them as strings/fixed-point, never `REAL`/float.
