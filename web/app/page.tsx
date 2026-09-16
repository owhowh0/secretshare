'use client'

import { useEffect, useState } from 'react'
import { fetchUser, getHeaders, handleCallback, logout, startLogin } from '../lib/auth'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? '/api'

export default function Page() {
  const [username, setUsername] = useState<string | null>(null)

  const [secret, setSecret] = useState('')
  const [createResult, setCreateResult] = useState<string | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createLoading, setCreateLoading] = useState(false)

  const [payloadId, setPayloadId] = useState('')
  const [retrieveResult, setRetrieveResult] = useState<string | null>(null)
  const [retrieveError, setRetrieveError] = useState<string | null>(null)
  const [retrieveLoading, setRetrieveLoading] = useState(false)

  useEffect(() => {
    async function init() {
      if (window.location.search.includes('code=')) {
        await handleCallback().catch(console.error)
      }
      const user = await fetchUser(API_BASE).catch(() => null)
      setUsername(user?.preferred_username ?? user?.sub ?? null)
    }
    init()
  }, [])

  async function handleLogin() {
    await startLogin().catch(err => alert('Failed to start login: ' + err.message))
  }

  function handleLogout() {
    logout()
    setUsername(null)
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
        body: JSON.stringify({ ciphertext: secret }),
      })
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const { payload_id } = await res.json()
      setCreateResult(payload_id)
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
      const res = await fetch(`${API_BASE}/secrets/${payloadId.trim()}`, {
        headers: getHeaders(),
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
          {username ? (
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
        <button id="create-btn" onClick={handleCreate} disabled={createLoading}>
          {createLoading ? 'Creating…' : 'Create'}
        </button>
        {createResult && <p className="muted">{createResult}</p>}
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
