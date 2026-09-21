'use client'

import { useState, useEffect, useCallback } from 'react'
import { useSession, signIn, signOut } from 'next-auth/react'
import {
  decryptAesGcm,
  decryptAesKeyWithRsa,
  encryptAesGcm,
  encryptAesKeyWithRsa,
  importPublicKeyFromSpkiPem,
} from '@/lib/crypto'
import {
  getOrGenerateDeviceKey,
  getStoredDeviceKey,
  updateStoredDeviceId,
} from '@/lib/key-store'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? '/api'

const TTL_OPTIONS = [
  { seconds: 300, label: '5 minutes' },
  { seconds: 600, label: '10 minutes' },
  { seconds: 3600, label: '1 hour' },
  { seconds: 86400, label: '24 hours' },
]

interface DeviceKeyItem {
  device_id: string
  platform: string
  public_key: string
  label?: string
}

export default function Page() {
  const { data: session, status } = useSession()
  const username = session?.user?.name ?? null

  // Device Onboarding State
  const [deviceRegistered, setDeviceRegistered] = useState(false)
  const [onboardingError, setOnboardingError] = useState<string | null>(null)

  // Creation State
  const [recipientId, setRecipientId] = useState('')
  const [secret, setSecret] = useState('')
  const [ttlSeconds, setTtlSeconds] = useState(600)
  const [createResult, setCreateResult] = useState<{ id: string; expiresAt: string } | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createLoading, setCreateLoading] = useState(false)

  // Reveal / Retrieval State
  const [payloadId, setPayloadId] = useState('')
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [retrieveResult, setRetrieveResult] = useState<string | null>(null)
  const [retrieveError, setRetrieveError] = useState<string | null>(null)
  const [retrieveLoading, setRetrieveLoading] = useState(false)

  const getHeaders = useCallback((): Record<string, string> => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const token = (session as any)?.accessToken
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    return headers
  }, [session])

  // Auto-onboard device on login, scoped by username
  useEffect(() => {
    if (status !== 'authenticated' || !session || !username) return

    async function onboardDevice() {
      try {
        const localKey = await getOrGenerateDeviceKey(username!, 'Web Browser')
        if (localKey.deviceId) {
          setDeviceRegistered(true)
          return
        }

        const res = await fetch(`${API_BASE}/keys/register`, {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify({
            public_key: localKey.spkiPem,
            platform: 'web',
            label: 'Web Browser',
          }),
        })

        if (!res.ok) {
          throw new Error(`Failed to register device key: ${res.statusText}`)
        }

        const data: DeviceKeyItem = await res.json()
        await updateStoredDeviceId(username!, data.device_id)
        setDeviceRegistered(true)
      } catch (err) {
        setOnboardingError(err instanceof Error ? err.message : 'Key registration failed')
      }
    }

    onboardDevice()
  }, [status, session, username, getHeaders])

  async function handleLogin() {
    await signIn('keycloak')
  }

  async function handleLogout() {
    await signOut()
  }

  async function handleCreate() {
    if (!recipientId.trim() || !secret.trim()) return
    setCreateLoading(true)
    setCreateResult(null)
    setCreateError(null)

    try {
      // 1. Fetch recipient's active public keys
      const keysRes = await fetch(`${API_BASE}/keys/${encodeURIComponent(recipientId.trim())}`, {
        headers: getHeaders(),
      })
      if (keysRes.status === 404) {
        throw new Error(`Recipient '${recipientId}' has no registered devices.`)
      }
      if (!keysRes.ok) {
        throw new Error(`Failed to fetch recipient public keys (${keysRes.status})`)
      }
      const { keys }: { keys: DeviceKeyItem[] } = await keysRes.json()
      if (!keys || keys.length === 0) {
        throw new Error(`Recipient '${recipientId}' has no active devices.`)
      }

      // 2. Encrypt plaintext with AES-256-GCM
      const { ciphertext, iv, rawAesKey } = await encryptAesGcm(secret)

      // 3. Encrypt AES key for each recipient device with RSA-OAEP
      const encryptedKeys = await Promise.all(
        keys.map(async (k) => {
          const rsaPublicKey = await importPublicKeyFromSpkiPem(k.public_key)
          const encryptedAesKey = await encryptAesKeyWithRsa(rawAesKey, rsaPublicKey)
          return {
            device_id: k.device_id,
            platform: k.platform,
            encrypted_aes_key: encryptedAesKey,
          }
        })
      )

      // 4. Post envelope to backend
      const res = await fetch(`${API_BASE}/secrets`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          recipient_id: recipientId.trim(),
          encrypted_keys: encryptedKeys,
          iv,
          ciphertext,
          ttl_seconds: ttlSeconds,
        }),
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

  // Check existence non-destructively before showing modal
  async function handlePreRevealCheck() {
    if (!payloadId.trim()) return
    setRetrieveLoading(true)
    setRetrieveError(null)
    setRetrieveResult(null)

    try {
      // Id in the body, not the URL, so it stays out of access logs (AUD-6).
      const res = await fetch(`${API_BASE}/secrets/exists`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ payload_id: payloadId.trim() }),
      })
      if (!res.ok) throw new Error(`Failed to check secret existence (${res.status})`)
      const { exists } = await res.json()
      if (!exists) {
        throw new Error('Secret not found or already retrieved.')
      }
      setShowConfirmModal(true)
    } catch (e) {
      setRetrieveError(e instanceof Error ? e.message : 'Check failed')
    } finally {
      setRetrieveLoading(false)
    }
  }

  // Authenticated reveal and local decryption
  async function handleConfirmReveal() {
    setShowConfirmModal(false)
    setRetrieveLoading(true)
    setRetrieveError(null)

    try {
      if (!username) {
        throw new Error('You must be logged in to reveal secrets.')
      }

      const localKey = await getStoredDeviceKey(username)
      if (!localKey) {
        throw new Error(`No local device key found for ${username}. Cannot decrypt secret.`)
      }

      // Atomically burn from server
      const res = await fetch(`${API_BASE}/secrets/reveal`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ payload_id: payloadId.trim() }),
      })

      if (res.status === 403) throw new Error('Forbidden: You are not the intended recipient.')
      if (res.status === 404) throw new Error('Secret not found or already retrieved.')
      if (!res.ok) throw new Error(`Server returned ${res.status}`)

      const envelope = await res.json()

      // Attempt to unwrap AES key across available recipient keys
      let rawAesKey: ArrayBuffer | null = null
      for (const encKey of envelope.encrypted_keys) {
        try {
          rawAesKey = await decryptAesKeyWithRsa(
            encKey.encrypted_aes_key,
            localKey.privateKey
          )
          if (rawAesKey) break
        } catch {
          // Continue trying other candidate keys
        }
      }

      if (!rawAesKey) {
        throw new Error('Could not decrypt secret: private key mismatch for this device.')
      }

      // Local AES-256-GCM decrypt in RAM
      const plaintext = await decryptAesGcm(envelope.ciphertext, envelope.iv, rawAesKey)

      setRetrieveResult(plaintext)
      setPayloadId('')
    } catch (e) {
      setRetrieveError(e instanceof Error ? e.message : 'Decryption failed')
    } finally {
      setRetrieveLoading(false)
    }
  }

  return (
    <main style={{ maxWidth: '640px', margin: '0 auto', padding: '2rem 1rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>SecretShare</h1>
        <div id="auth-section">
          {status === 'authenticated' && username ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span className="muted">{username}</span>
              <button
                id="logout-btn"
                onClick={handleLogout}
                style={{ background: '#333', fontSize: '0.85rem', padding: '0.4rem 0.8rem', cursor: 'pointer' }}
              >
                Logout
              </button>
            </div>
          ) : (
            <button id="login-btn" onClick={handleLogin} style={{ cursor: 'pointer' }}>
              Login with Keycloak
            </button>
          )}
        </div>
      </header>

      {onboardingError && <p className="error" style={{ color: '#e53e3e' }}>Device Key Warning: {onboardingError}</p>}
      {deviceRegistered && <p className="muted" style={{ fontSize: '0.8rem', color: '#38a169' }}>Device key registered & ready for E2E encryption.</p>}

      <hr style={{ margin: '1.5rem 0' }} />

      <section>
        <h2>Create Secret (E2E Encrypted)</h2>
        <input
          type="text"
          value={recipientId}
          onChange={(e) => setRecipientId(e.target.value)}
          placeholder="Recipient Username (Keycloak)"
          style={{ width: '100%', marginBottom: '0.75rem', padding: '0.5rem' }}
        />
        <textarea
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          rows={5}
          placeholder="Type your secret here…"
          style={{ width: '100%', padding: '0.5rem' }}
        />
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
          <select
            id="ttl-select"
            value={ttlSeconds}
            onChange={(e) => setTtlSeconds(Number(e.target.value))}
            style={{ padding: '0.4rem' }}
          >
            {TTL_OPTIONS.map((o) => (
              <option key={o.seconds} value={o.seconds}>
                Expires in {o.label}
              </option>
            ))}
          </select>
          <button
            id="create-btn"
            onClick={handleCreate}
            disabled={createLoading || !secret.trim() || !recipientId.trim()}
            style={{ padding: '0.4rem 1rem', cursor: 'pointer' }}
          >
            {createLoading ? 'Encrypting & Creating…' : 'Encrypt & Share'}
          </button>
        </div>
        {createResult && (
          <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#f7fafc', border: '1px solid #e2e8f0', borderRadius: '4px' }}>
            <p style={{ margin: 0, fontWeight: 'bold' }}>Secret Payload ID:</p>
            <code style={{ wordBreak: 'break-all' }}>{createResult.id}</code>
            <p className="muted" style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem' }}>
              Expires {createResult.expiresAt}
            </p>
          </div>
        )}
        {createError && <p className="error" style={{ color: '#e53e3e', marginTop: '0.5rem' }}>{createError}</p>}
      </section>

      <hr style={{ margin: '1.5rem 0' }} />

      <section>
        <h2>Retrieve Secret</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            value={payloadId}
            onChange={(e) => setPayloadId(e.target.value)}
            placeholder="Payload ID"
            style={{ flex: 1, padding: '0.5rem' }}
          />
          <button
            id="retrieve-btn"
            onClick={handlePreRevealCheck}
            disabled={retrieveLoading || !payloadId.trim()}
            style={{ padding: '0.5rem 1rem', cursor: 'pointer' }}
          >
            {retrieveLoading ? 'Verifying…' : 'Reveal Secret'}
          </button>
        </div>

        {retrieveResult && (
          <div style={{ marginTop: '1rem', padding: '1rem', background: '#f0fff4', border: '1px solid #c6f6d5', borderRadius: '4px' }}>
            <p style={{ margin: '0 0 0.5rem 0', fontWeight: 'bold', color: '#22543d' }}>Decrypted Secret Plaintext:</p>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{retrieveResult}</pre>
          </div>
        )}
        {retrieveError && <p className="error" style={{ color: '#e53e3e', marginTop: '0.5rem' }}>{retrieveError}</p>}
      </section>

      {/* Safe Reveal Warning Modal */}
      {showConfirmModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: '#fff',
              padding: '1.5rem',
              borderRadius: '8px',
              maxWidth: '450px',
              width: '90%',
              boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
            }}
          >
            <h3 style={{ marginTop: 0, color: '#c53030' }}>Burn-After-Reading Warning</h3>
            <p style={{ color: '#4a5568', lineHeight: 1.5 }}>
              This secret is stored ephemerally. Revealing it will <strong>permanently and irreversibly destroy</strong> it from the server.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
              <button
                onClick={() => setShowConfirmModal(false)}
                style={{ padding: '0.5rem 1rem', background: '#e2e8f0', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReveal}
                style={{ padding: '0.5rem 1rem', background: '#e53e3e', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
              >
                Reveal & Burn
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
