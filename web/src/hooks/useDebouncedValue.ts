import { useEffect, useState } from 'react'

const DEFAULT_DELAY_MS = 300

/** Delays reflecting a fast-changing value (a search box's `onChange`) until
 * it's stopped changing for `delayMs` - used before free-text filters hit
 * the server (accounts' search box, quotes/invoices' account-name filter),
 * so typing doesn't fire a request per keystroke. Discrete inputs (a status
 * dropdown, a page click) skip this and apply immediately. */
export function useDebouncedValue<T>(value: T, delayMs = DEFAULT_DELAY_MS): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}
