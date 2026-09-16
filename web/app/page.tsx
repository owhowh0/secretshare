'use client'

import { useState } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? '/api'

export default function Page() {
  const [secret, setSecret] = useState('')
  const [createResult, setCreateResult] = useState<string | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createLoading, setCreateLoading] = useState(false)

  const [payloadId, setPayloadId] = useState('')
  const [retrieveResult, setRetrieveResult] = useState<string | null>(null)
  const [retrieveError, setRetrieveError] = useState<string | null>(null)
  const [retrieveLoading, setRetrieveLoading] = useState(false)

  async function handleCreate() {
    if (!secret.trim()) return
    setCreateLoading(true)
    setCreateResult(null)
    setCreateError(null)
    try {
      const res = await fetch(`${API_BASE}/secrets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ciphertext: secret }),
      })
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const { payload_id } = await res.json()
      setCreateResult(payload_id)
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
      const res = await fetch(`${API_BASE}/secrets/${payloadId.trim()}`)
      if (res.status === 404) throw new Error('Secret not found.')
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const { ciphertext } = await res.json()
      setRetrieveResult(ciphertext)
    } catch (e) {
      setRetrieveError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setRetrieveLoading(false)
    }
  }

  return (
    <main>
      <section>
        <h2>Create secret</h2>
        <textarea
          value={secret}
          onChange={e => setSecret(e.target.value)}
          rows={5}
          placeholder="Type your secret here…"
        />
        <button onClick={handleCreate} disabled={createLoading}>
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
        <button onClick={handleRetrieve} disabled={retrieveLoading}>
          {retrieveLoading ? 'Retrieving…' : 'Retrieve'}
        </button>
        {retrieveResult && <pre>{retrieveResult}</pre>}
        {retrieveError && <p className="error">{retrieveError}</p>}
      </section>
    </main>
  )
}
