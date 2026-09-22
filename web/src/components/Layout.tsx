import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTheme } from '../hooks/useTheme'
import { CloseIcon, CogIcon, MenuIcon, MoonIcon, SunIcon } from './icons'

export function Layout() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [isMenuOpen, setIsMenuOpen] = useState(false)

  function closeMenu() {
    setIsMenuOpen(false)
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="brand">Invoice System</span>
        <button
          type="button"
          className="icon-button nav-toggle"
          onClick={() => setIsMenuOpen((open) => !open)}
          aria-expanded={isMenuOpen}
          aria-controls="app-nav-drawer"
          aria-label={isMenuOpen ? 'Close menu' : 'Open menu'}
        >
          {isMenuOpen ? <CloseIcon /> : <MenuIcon />}
        </button>
        <div id="app-nav-drawer" className="app-nav-drawer" data-open={isMenuOpen}>
          <nav>
            <NavLink to="/" end onClick={closeMenu}>
              Home
            </NavLink>
            <NavLink to="/accounts" onClick={closeMenu}>
              Accounts
            </NavLink>
            <NavLink to="/domains" onClick={closeMenu}>
              Domains
            </NavLink>
            <NavLink to="/quotes" onClick={closeMenu}>
              Quotes
            </NavLink>
            <NavLink to="/invoices" onClick={closeMenu}>
              Invoices
            </NavLink>
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
            <NavLink
              className="button icon-button"
              to="/settings"
              aria-label="Settings"
              title="Settings"
              onClick={closeMenu}
            >
              <CogIcon />
            </NavLink>
            <span>{user?.email}</span>
            <button
              type="button"
              onClick={() => {
                closeMenu()
                logout()
              }}
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  )
}
