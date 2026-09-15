import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AccountsPage } from './pages/AccountsPage'
import { InvoiceDetailPage } from './pages/InvoiceDetailPage'
import { InvoicesPage } from './pages/InvoicesPage'
import { LoginPage } from './pages/LoginPage'
import { QuoteDetailPage } from './pages/QuoteDetailPage'
import { QuoteNewPage } from './pages/QuoteNewPage'
import { QuotesPage } from './pages/QuotesPage'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/accounts" replace />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/quotes" element={<QuotesPage />} />
          <Route path="/quotes/new" element={<QuoteNewPage />} />
          <Route path="/quotes/:id" element={<QuoteDetailPage />} />
          <Route path="/invoices" element={<InvoicesPage />} />
          <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
