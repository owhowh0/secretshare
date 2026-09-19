'use client'

import { useState } from 'react'
import { useSession, signIn, signOut } from 'next-auth/react'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? '/api'

// Must stay within the API's SECRET_TTL_MIN_SECONDS..SECRET_TTL_MAX_SECONDS.
const TTL_OPTIONS = [
  { seconds: 300, label: '5 minutes' },
  { seconds: 600, label: '10 minutes' },
  { seconds: 3600, label: '1 hour' },
  { seconds: 86400, label: '24 hours' },
]

export default function Page() {
  const { data: session, status } = useSession()
  const username = session?.user?.name ?? null

  const [secret, setSecret] = useState('')
  const [ttlSeconds, setTtlSeconds] = useState(600)
  const [createResult, setCreateResult] = useState<{ id: string; expiresAt: string } | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createLoading, setCreateLoading] = useState(false)

  const [payloadId, setPayloadId] = useState('')
  const [retrieveResult, setRetrieveResult] = useState<string | null>(null)
  const [retrieveError, setRetrieveError] = useState<string | null>(null)
  const [retrieveLoading, setRetrieveLoading] = useState(false)

  const getHeaders = (): Record<string, string> => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const token = (session as any)?.accessToken
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    return headers
  }

  async function handleLogin() {
    await signIn('keycloak')
  }

  async function handleLogout() {
    await signOut()
  }

  async function handleCreate() {
    if (!secret.trim()) return
    setCreateLoading(true)
    setCreateResult(null)
    setCreateError(null)
    try {
      const res = await fetch(`${API_BASE}/secrets`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ ciphertext: secret, ttl_seconds: ttlSeconds }),
      })
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const { payload_id, expires_at } = await res.json()
      setCreateResult({ id: payload_id, expiresAt: new Date(expires_at).toLocaleString() })
      setSecret('')
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setCreateLoading(false)
    }
  }

  async function handleRetrieve() {
    if (!payloadId.trim()) return
    setRetrieveLoading(true)
    setRetrieveResult(null)
    setRetrieveError(null)
    try {
      // The id goes in the body, not the URL: a path id would be recorded by
      // the access log, any proxy in front of it, and browser history (AUD-6).
      const res = await fetch(`${API_BASE}/secrets/reveal`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ payload_id: payloadId.trim() }),
      })
      if (res.status === 404) throw new Error('Secret not found.')
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const { ciphertext } = await res.json()
      setRetrieveResult(ciphertext)
      setPayloadId('')
    } catch (e) {
      setRetrieveError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setRetrieveLoading(false)
    }
  }

  return (
    <main>
      <header>
        <h1>SecretShare</h1>
        <div id="auth-section">
          {status === 'authenticated' && username ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span className="muted">{username}</span>
              <button id="logout-btn" onClick={handleLogout} style={{ background: '#333', fontSize: '0.85rem', padding: '0.4rem 0.8rem' }}>
                Logout
              </button>
            </div>
          ) : (
            <button id="login-btn" onClick={handleLogin}>Login with Keycloak</button>
          )}
        </div>
      </header>

      <hr />

      <section>
        <h2>Create secret</h2>
        <textarea
          value={secret}
          onChange={e => setSecret(e.target.value)}
          rows={5}
          placeholder="Type your secret here…"
        />
        <select id="ttl-select" value={ttlSeconds} onChange={e => setTtlSeconds(Number(e.target.value))}>
          {TTL_OPTIONS.map(o => (
            <option key={o.seconds} value={o.seconds}>
              Expires in {o.label}
            </option>
          ))}
        </select>
        <button id="create-btn" onClick={handleCreate} disabled={createLoading}>
          {createLoading ? 'Creating…' : 'Create'}
        </button>
        {createResult && (
          <p className="muted">
            {createResult.id}
            <br />
            Expires {createResult.expiresAt}
          </p>
        )}
        {createError && <p className="error">{createError}</p>}
      </section>

      <hr />

      <section>
        <h2>Retrieve secret</h2>
        <input
          type="text"
          value={payloadId}
          onChange={e => setPayloadId(e.target.value)}
          placeholder="Payload ID"
        />
        <button id="retrieve-btn" onClick={handleRetrieve} disabled={retrieveLoading}>
          {retrieveLoading ? 'Retrieving…' : 'Retrieve'}
        </button>
        {retrieveResult && <pre>{retrieveResult}</pre>}
        {retrieveError && <p className="error">{retrieveError}</p>}
      </section>
    </main>
  )
}
