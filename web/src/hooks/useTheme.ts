import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const THEME_STORAGE_KEY = 'invoice-system-theme'

function getInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // localStorage can throw in private-browsing/storage-blocked contexts -
    // fall through to the system preference below instead of crashing.
  }
  // matchMedia isn't implemented in every environment (jsdom in tests, some
  // older browsers) - fall back to light rather than throwing.
  if (typeof window.matchMedia !== 'function') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/**
 * A manual light/dark override on top of the CSS `prefers-color-scheme`
 * default (see index.css's `:root[data-theme]` rules) - once toggled, the
 * choice persists across reloads via localStorage rather than continuing
 * to track the OS setting.
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch {
      // Nothing to persist to - the theme still applies for this page load.
    }
  }, [theme])

  const toggleTheme = () => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))

  return { theme, toggleTheme }
}
