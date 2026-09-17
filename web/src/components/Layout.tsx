import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTheme } from '../hooks/useTheme'
import { CogIcon, MoonIcon, SunIcon } from './icons'

export function Layout() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="brand">Invoice System</span>
        <nav>
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/accounts">Accounts</NavLink>
          <NavLink to="/quotes">Quotes</NavLink>
          <NavLink to="/invoices">Invoices</NavLink>
        </nav>
        <div className="user-menu">
          <button
            type="button"
            className="icon-button"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? <MoonIcon /> : <SunIcon />}
          </button>
          <NavLink className="button icon-button" to="/settings" aria-label="Settings" title="Settings">
            <CogIcon />
          </NavLink>
          <span>{user?.email}</span>
          <button type="button" onClick={logout}>
            Log out
          </button>
        </div>
      </header>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  )
}
