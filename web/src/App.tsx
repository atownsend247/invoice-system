import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AccountDetailPage } from './pages/AccountDetailPage'
import { AccountsPage } from './pages/AccountsPage'
import { ExpenseDetailPage } from './pages/ExpenseDetailPage'
import { ExpenseNewPage } from './pages/ExpenseNewPage'
import { HomePage } from './pages/HomePage'
import { InvoiceDetailPage } from './pages/InvoiceDetailPage'
import { InvoicesPage } from './pages/InvoicesPage'
import { LoginPage } from './pages/LoginPage'
import { QuoteDetailPage } from './pages/QuoteDetailPage'
import { QuoteNewPage } from './pages/QuoteNewPage'
import { QuotesPage } from './pages/QuotesPage'
import { RegisterPage } from './pages/RegisterPage'
import { SettingsPage } from './pages/SettingsPage'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/accounts/:id" element={<AccountDetailPage />} />
          <Route path="/quotes" element={<QuotesPage />} />
          <Route path="/quotes/new" element={<QuoteNewPage />} />
          <Route path="/quotes/:id" element={<QuoteDetailPage />} />
          <Route path="/invoices" element={<InvoicesPage />} />
          <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
          <Route path="/expenses/new" element={<ExpenseNewPage />} />
          <Route path="/expenses/:id" element={<ExpenseDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
