import { useCallback, useEffect, useState } from 'react'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

/** The one shared "call an async function, track loading/error/data" hook -
 * see CLAUDE.md conventions. `deps` re-runs the fetch; `refetch()` re-runs it
 * without a dependency changing (e.g. after a mutation). */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> & { refetch: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState((previous) => ({ ...previous, loading: true, error: null }))
    fn()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null })
      })
      .catch((err: unknown) => {
        if (!cancelled) setState({ data: null, loading: false, error: errorMessage(err) })
      })
    return () => {
      cancelled = true
    }
    // fn is re-created by callers each render on purpose (it closes over
    // arguments like an id) - deps is the real dependency list, not fn.
  }, [...deps, version])

  const refetch = useCallback(() => setVersion((v) => v + 1), [])

  return { ...state, refetch }
}

export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  return 'Something went wrong'
}
