/** Today as a local-timezone ISO date (`YYYY-MM-DD`), for pre-filling a
 * date input - deliberately not `toISOString()` (UTC), which can show the
 * wrong calendar date to a user whose local time has already crossed
 * midnight into a new day but UTC hasn't yet, or vice versa. */
export function todayLocalDate(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}
