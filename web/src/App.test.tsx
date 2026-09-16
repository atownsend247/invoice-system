import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from './api'
import { App } from './App'
import { AuthProvider } from './auth/AuthContext'

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>()
  return {
    ...actual,
    login: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
    listAccounts: vi.fn(),
    listInvoices: vi.fn(),
    getMonthlyInvoiceTotals: vi.fn(),
    getMonthlyExpenseTotals: vi.fn(),
    getStats: vi.fn(),
  }
})

const mockedApi = vi.mocked(api)

function renderApp(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('App', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('redirects an unauthenticated visitor to the login page', async () => {
    renderApp('/accounts')

    expect(await screen.findByRole('heading', { name: 'Invoice System' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
  })

  it('logs in and lands on the home page', async () => {
    mockedApi.login.mockResolvedValue({
      token: 'tok_123',
      expires_at: '2026-10-01T00:00:00Z',
      user: {
        id: 'user-1',
        email: 'owner@acme.test',
        name: 'owner',
        created_at: '2026-01-01T00:00:00Z',
        totp_enabled: false,
      },
    })
    mockedApi.listAccounts.mockResolvedValue([])
    mockedApi.listInvoices.mockResolvedValue([])
    mockedApi.getMonthlyInvoiceTotals.mockResolvedValue({ currency: 'GBP', months: [] })
    mockedApi.getMonthlyExpenseTotals.mockResolvedValue({ currency: 'GBP', months: [] })
    mockedApi.getStats.mockResolvedValue({
      account_count: 0,
      quote_count: 0,
      invoice_count: 0,
      quotes_sent_count: 0,
      quotes_converted_count: 0,
      total_paid: '0',
      currency: 'GBP',
    })

    renderApp('/login')
    const user = userEvent.setup()

    await user.type(screen.getByLabelText('Email'), 'owner@acme.test')
    await user.type(screen.getByLabelText('Password'), 'correct horse battery staple')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Home' })).toBeInTheDocument()
    expect(mockedApi.login).toHaveBeenCalledWith('owner@acme.test', 'correct horse battery staple', undefined)
  })

  it('shows the server error and stays on the login page on bad credentials', async () => {
    mockedApi.login.mockRejectedValue(new api.ApiError(401, 'incorrect email or password'))

    renderApp('/login')
    const user = userEvent.setup()

    await user.type(screen.getByLabelText('Email'), 'owner@acme.test')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('incorrect email or password')
  })
})
