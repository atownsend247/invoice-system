import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import * as api from '../api'
import { errorMessage } from '../hooks/useAsync'

export function RegisterPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const navigate = useNavigate()

  const [checking, setChecking] = useState(true)
  const [valid, setValid] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!token) {
      setChecking(false)
      return
    }
    let cancelled = false
    api
      .checkRegistrationInvite(token)
      .then(() => {
        if (!cancelled) setValid(true)
      })
      .catch(() => {
        if (!cancelled) setValid(false)
      })
      .finally(() => {
        if (!cancelled) setChecking(false)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!token) return
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      await api.register(token, email, password)
      navigate('/login', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (checking) {
    return (
      <div className="login-page">
        <p>Loading…</p>
      </div>
    )
  }

  if (!token || !valid) {
    return (
      <div className="login-page">
        <div className="login-form">
          <h1>Invoice System</h1>
          <p className="form-error" role="alert">
            This registration link is invalid or has expired.
          </p>
          <p>
            <Link to="/login">Back to login</Link>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>Create your account</h1>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            autoFocus
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={8}
            required
          />
        </label>
        <label>
          Confirm password
          <input
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            minLength={8}
            required
          />
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Creating…' : 'Create account'}
        </button>
      </form>
    </div>
  )
}
