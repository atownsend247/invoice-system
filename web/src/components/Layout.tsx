import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="brand">Invoice System</span>
        <nav>
          <NavLink to="/accounts">Accounts</NavLink>
          <NavLink to="/quotes">Quotes</NavLink>
          <NavLink to="/invoices">Invoices</NavLink>
        </nav>
        <div className="user-menu">
          <NavLink to="/settings">Settings</NavLink>
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
