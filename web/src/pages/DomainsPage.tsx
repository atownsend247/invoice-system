import { useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api'
import { DomainForm } from '../components/DomainForm'
import { RegistrarForm } from '../components/RegistrarForm'
import { errorMessage, useAsync } from '../hooks/useAsync'
import type { Domain, Registrar } from '../types'

function registrarUsageLabel(registrar: Registrar): string {
  if (registrar.domain_count === 0) return 'No domains'
  const domains = `${registrar.domain_count} domain${registrar.domain_count === 1 ? '' : 's'}`
  const accounts = `${registrar.account_count} account${registrar.account_count === 1 ? '' : 's'}`
  return `${domains} (${accounts})`
}

/** The central place to manage domains and registrars - domains used to
 * only exist nested under an Account (created via "Add domain" on
 * AccountDetailPage.tsx); now they're organisation-wide like Registrar
 * always was, and an account only *links* to one that already exists here
 * (see AccountDetailPage.tsx's "Link domain" action and CLAUDE.md). Two
 * stacked sections on one page, not sub-tabs - avoids reintroducing the
 * shared-tab-state issues just fixed on the Settings page. */
export function DomainsPage() {
  return (
    <section>
      <h1>Domains</h1>
      <p className="meta">Manage the domains and registrars your business tracks.</p>
      <DomainsSection />
      <RegistrarsSection />
    </section>
  )
}

function DomainsSection() {
  const { data: domains, refetch } = useAsync(() => api.listDomains(), [])
  // Fetched once here, not per DomainForm instance - see DomainForm.tsx's
  // own comment on why it takes this as a prop instead of fetching it
  // itself.
  const { data: registrars } = useAsync(() => api.listRegistrars(), [])
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleDelete(domain: Domain) {
    setError(null)
    setDeletingId(domain.id)
    try {
      await api.deleteDomain(domain.id)
      refetch()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="dashboard-section">
      <fieldset className="form-section">
        <legend>Domains</legend>
        <div className="page-header">
          <p className="meta">
            A domain can exist here before it's ever linked to a client - link it from that client's own account
            page.
          </p>
          {!adding && (
            <button type="button" onClick={() => setAdding(true)}>
              Add domain
            </button>
          )}
        </div>
        {adding && (
          <DomainForm
            registrars={registrars ?? []}
            submitLabel="Add"
            submittingLabel="Adding…"
            onSubmit={(input) => api.createDomain(input)}
            onDone={() => {
              setAdding(false)
              refetch()
            }}
            onCancel={() => setAdding(false)}
          />
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {!domains && <p>Loading…</p>}
        {domains && domains.length === 0 && <p className="meta">No domains recorded yet.</p>}
        {domains && domains.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Domain</th>
                  <th>Expires</th>
                  <th>Registrar</th>
                  <th>Auto-renew</th>
                  <th>Linked account</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {domains.map((domain) =>
                  editingId === domain.id ? (
                    <tr key={domain.id}>
                      <td colSpan={6}>
                        <DomainForm
                          initial={domain}
                          registrars={registrars ?? []}
                          submitLabel="Save"
                          submittingLabel="Saving…"
                          onSubmit={(input) => api.updateDomain(domain.id, input)}
                          onDone={() => {
                            setEditingId(null)
                            refetch()
                          }}
                          onCancel={() => setEditingId(null)}
                        />
                      </td>
                    </tr>
                  ) : (
                    <tr key={domain.id}>
                      <td>{domain.domain_name}</td>
                      <td>{domain.expiry_date}</td>
                      <td>{domain.registrar}</td>
                      <td>{domain.auto_renew ? 'Yes' : 'No'}</td>
                      <td>
                        {domain.account_id ? (
                          <Link to={`/accounts/${domain.account_id}`}>{domain.account_name}</Link>
                        ) : (
                          <span className="meta">Unlinked</span>
                        )}
                      </td>
                      <td>
                        <button type="button" onClick={() => setEditingId(domain.id)}>
                          Edit
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => handleDelete(domain)}
                          disabled={deletingId === domain.id}
                        >
                          {deletingId === domain.id ? 'Deleting…' : 'Delete'}
                        </button>
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </fieldset>
    </div>
  )
}

/** Moved verbatim from SettingsPage.tsx's old Registrars tab - see
 * CLAUDE.md. No tabpanel wrapper needed here (no tab system on this
 * page), otherwise unchanged. */
function RegistrarsSection() {
  const { data: registrars, refetch } = useAsync(() => api.listRegistrars(), [])
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleDelete(registrar: Registrar) {
    setError(null)
    setDeletingId(registrar.id)
    try {
      await api.deleteRegistrar(registrar.id)
      refetch()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="dashboard-section">
      <fieldset className="form-section">
        <legend>Registrars</legend>
        <div className="page-header">
          <p className="meta">Populates the Registrar dropdown when adding a domain.</p>
          {!adding && (
            <button type="button" onClick={() => setAdding(true)}>
              Add registrar
            </button>
          )}
        </div>
        {adding && (
          <RegistrarForm
            submitLabel="Add"
            submittingLabel="Adding…"
            onSubmit={(input) => api.createRegistrar(input)}
            onDone={() => {
              setAdding(false)
              refetch()
            }}
            onCancel={() => setAdding(false)}
          />
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {!registrars && <p>Loading…</p>}
        {registrars && registrars.length === 0 && <p className="meta">No registrars configured yet.</p>}
        {registrars && registrars.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Notes</th>
                  <th>Domains</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {registrars.map((registrar) =>
                  editingId === registrar.id ? (
                    <tr key={registrar.id}>
                      <td colSpan={4}>
                        <RegistrarForm
                          initial={registrar}
                          submitLabel="Save"
                          submittingLabel="Saving…"
                          onSubmit={(input) => api.updateRegistrar(registrar.id, input)}
                          onDone={() => {
                            setEditingId(null)
                            refetch()
                          }}
                          onCancel={() => setEditingId(null)}
                        />
                      </td>
                    </tr>
                  ) : (
                    <tr key={registrar.id}>
                      <td>{registrar.name}</td>
                      <td>{registrar.notes ?? '—'}</td>
                      <td>{registrarUsageLabel(registrar)}</td>
                      <td>
                        <button type="button" onClick={() => setEditingId(registrar.id)}>
                          Edit
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => handleDelete(registrar)}
                          disabled={deletingId === registrar.id || registrar.domain_count > 0}
                          title={
                            registrar.domain_count > 0
                              ? `Still used by ${registrarUsageLabel(registrar)} - remove or reassign them first`
                              : undefined
                          }
                        >
                          {deletingId === registrar.id ? 'Deleting…' : 'Delete'}
                        </button>
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </fieldset>
    </div>
  )
}
