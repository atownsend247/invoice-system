import type { Account } from './types'

/** address_line1 is always present (required, see types.ts); the rest are
 * each independently optional, same filtering as the backend's
 * pdf.py:account_address_lines - kept as a pure function so both
 * AccountsPage's list column and AccountDetailPage's read-only view render
 * the same address consistently. */
export function accountAddressLines(account: Account): string[] {
  const optional = [account.address_line2, account.town_or_city, account.county, account.postcode]
  return [account.address_line1, ...optional.filter((line): line is string => Boolean(line?.trim()))]
}
