import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, defaultApiBaseUrl, getAccount, login, setAuthToken, setUnauthorizedHandler } from './api'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    setAuthToken(null)
    setUnauthorizedHandler(null)
    vi.unstubAllGlobals()
  })

  it('attaches the Authorization header once a token is set', async () => {
    setAuthToken('tok_123')
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(200, { id: 'acc-1', business_name: 'Acme' }))

    await getAccount('acc-1')

    const [, options] = vi.mocked(fetch).mock.calls[0]
    const headers = new Headers(options?.headers)
    expect(headers.get('Authorization')).toBe('Bearer tok_123')
  })

  it('does not attach an Authorization header when logged out', async () => {
    setAuthToken(null)
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(200, { id: 'acc-1', business_name: 'Acme' }))

    await getAccount('acc-1')

    const [, options] = vi.mocked(fetch).mock.calls[0]
    const headers = new Headers(options?.headers)
    expect(headers.has('Authorization')).toBe(false)
  })

  it('throws an ApiError carrying the status and server detail on failure', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(404, { detail: 'account 999 not found' }))

    await expect(getAccount('does-not-exist')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: 'account 999 not found',
    })
  })

  it('calls the unauthorized handler on a 401 from a protected route', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(401, { detail: 'not authenticated' }))

    await expect(getAccount('acc-1')).rejects.toBeInstanceOf(ApiError)
    expect(handler).toHaveBeenCalledOnce()
  })

  it('does not call the unauthorized handler for a failed login itself', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(401, { detail: 'incorrect email or password' }))

    await expect(login('a@b.test', 'wrong')).rejects.toBeInstanceOf(ApiError)
    expect(handler).not.toHaveBeenCalled()
  })
})

describe('defaultApiBaseUrl', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('defaults to 127.0.0.1 when the page itself was loaded from localhost', () => {
    vi.stubGlobal('location', { hostname: 'localhost', protocol: 'http:' })
    expect(defaultApiBaseUrl()).toBe('http://127.0.0.1:8000')
  })

  it('defaults to 127.0.0.1 when the page itself was loaded from 127.0.0.1', () => {
    vi.stubGlobal('location', { hostname: '127.0.0.1', protocol: 'http:' })
    expect(defaultApiBaseUrl()).toBe('http://127.0.0.1:8000')
  })

  it('follows the page onto a LAN host instead, for npm run dev:lan', () => {
    vi.stubGlobal('location', { hostname: '192.168.1.23', protocol: 'http:' })
    expect(defaultApiBaseUrl()).toBe('http://192.168.1.23:8000')
  })
})
