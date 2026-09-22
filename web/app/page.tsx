'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
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

/** Attach .released class for the bounce-back keyframe, remove after it fires. */
function triggerBounce(el: HTMLElement | null) {
  if (!el) return
  el.classList.remove('released')
  // Force reflow so the class can be re-added
  void el.offsetWidth
  el.classList.add('released')
  el.addEventListener('animationend', () => el.classList.remove('released'), { once: true })
}

/** Attach .shake class, remove after animation completes so it can re-trigger. */
function triggerShake(el: HTMLElement | null) {
  if (!el) return
  el.classList.remove('shake')
  void el.offsetWidth
  el.classList.add('shake')
  el.addEventListener('animationend', () => el.classList.remove('shake'), { once: true })
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
  const [createResult, setCreateResult] = useState<{
    id: string
    expiresAt: string
    link: string
  } | null>(null)
  const [copiedLink, setCopiedLink] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [createLoading, setCreateLoading] = useState(false)

  // Reveal / Retrieval State
  const [payloadId, setPayloadId] = useState('')
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [retrieveResult, setRetrieveResult] = useState<string | null>(null)
  const [retrieveError, setRetrieveError] = useState<string | null>(null)
  const [retrieveLoading, setRetrieveLoading] = useState(false)

  // Refs for shake / bounce targets
  const createBtnRef = useRef<HTMLButtonElement>(null)
  const retrieveBtnRef = useRef<HTMLButtonElement>(null)
  const copyBtnRef = useRef<HTMLButtonElement>(null)

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

  // Check existence non-destructively before showing modal
  const handlePreRevealCheck = useCallback(async (explicitId?: string) => {
    const idToUse = (typeof explicitId === 'string' ? explicitId : payloadId).trim()
    if (!idToUse) {
      triggerShake(retrieveBtnRef.current)
      return
    }
    setRetrieveLoading(true)
    setRetrieveError(null)
    setRetrieveResult(null)

    try {
      // Id in the body, not the URL, so it stays out of access logs (AUD-6).
      const res = await fetch(`${API_BASE}/secrets/exists`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ payload_id: idToUse }),
      })
      if (!res.ok) throw new Error(`Failed to check secret existence (${res.status})`)
      const { exists } = await res.json()
      if (!exists) {
        throw new Error('Secret not found or already retrieved.')
      }
      setPayloadId(idToUse)
      setShowConfirmModal(true)
    } catch (e) {
      setRetrieveError(e instanceof Error ? e.message : 'Check failed')
      triggerShake(retrieveBtnRef.current)
    } finally {
      setRetrieveLoading(false)
    }
  }, [payloadId, getHeaders])

  // Detect secret link or ID in URL (?id=..., ?payload_id=..., #...) and trigger burning notice
  useEffect(() => {
    if (typeof window === 'undefined') return
    if (status === 'loading') return

    const searchParams = new URLSearchParams(window.location.search)
    let urlId = searchParams.get('id') || searchParams.get('payload_id')

    if (!urlId && window.location.hash) {
      const hash = window.location.hash.slice(1)
      if (hash.startsWith('id=')) {
        urlId = hash.slice(3)
      } else if (hash.length > 0 && !hash.includes('/')) {
        urlId = hash
      }
    }

    if (urlId && urlId.trim()) {
      const cleanId = urlId.trim()
      setPayloadId(cleanId)
      handlePreRevealCheck(cleanId)
    }
  }, [status, handlePreRevealCheck])

  async function handleLogin() {
    const callbackUrl = typeof window !== 'undefined' ? window.location.href : undefined
    await signIn('keycloak', callbackUrl ? { callbackUrl } : undefined)
  }

  async function handleLogout() {
    await signOut()
  }

  async function handleCreate() {
    if (!recipientId.trim() || !secret.trim()) {
      triggerShake(createBtnRef.current)
      return
    }
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

      const origin = typeof window !== 'undefined' ? window.location.origin : ''
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? ''
      const link = `${origin}${basePath}/?id=${encodeURIComponent(payload_id)}`

      setCreateResult({
        id: payload_id,
        expiresAt: new Date(expires_at).toLocaleString(),
        link,
      })
      setSecret('')
      triggerBounce(createBtnRef.current)
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Unknown error')
      triggerShake(createBtnRef.current)
    } finally {
      setCreateLoading(false)
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

      // Clean up URL query / hash to avoid re-triggering check on page refresh
      if (typeof window !== 'undefined') {
        const url = new URL(window.location.href)
        if (url.searchParams.has('id') || url.searchParams.has('payload_id')) {
          url.searchParams.delete('id')
          url.searchParams.delete('payload_id')
          window.history.replaceState({}, '', url.pathname + (url.hash || ''))
        }
      }
    } catch (e) {
      setRetrieveError(e instanceof Error ? e.message : 'Decryption failed')
    } finally {
      setRetrieveLoading(false)
    }
  }

  return (
    <main className="app-main">
      {/* ── Header ── */}
      <header className="app-header">
        <h1>SecretShare</h1>
        <div id="auth-section">
          {status === 'authenticated' && username ? (
            <div className="row">
              <span className="muted">{username}</span>
              <button
                id="logout-btn"
                className="btn btn-ghost"
                onClick={handleLogout}
                onPointerUp={(e) => triggerBounce(e.currentTarget)}
              >
                Logout
              </button>
            </div>
          ) : (
            <button
              id="login-btn"
              className="btn"
              onClick={handleLogin}
              onPointerUp={(e) => triggerBounce(e.currentTarget)}
            >
              Login with Keycloak
            </button>
          )}
        </div>
      </header>

      {/* ── Device status ── */}
      {onboardingError && (
        <p className="error-box">Device key warning: {onboardingError}</p>
      )}
      {deviceRegistered && (
        <p className="status-ok">&#x2713; Device key registered — E2E encryption ready</p>
      )}

      <hr className="divider" />

      {/* ── Create Secret ── */}
      <section className="glass" style={{ borderRadius: '16px', padding: '1.25rem' }}>
        <h2>Create Secret</h2>
        <div className="col">
          <input
            type="text"
            value={recipientId}
            onChange={(e) => setRecipientId(e.target.value)}
            placeholder="Recipient username (Keycloak)"
            style={{ width: '100%' }}
          />
          <textarea
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            rows={5}
            placeholder="Type your secret here…"
            style={{ width: '100%', resize: 'vertical' }}
          />
          <div className="row">
            <select
              id="ttl-select"
              value={ttlSeconds}
              onChange={(e) => setTtlSeconds(Number(e.target.value))}
              style={{ flexShrink: 0 }}
            >
              {TTL_OPTIONS.map((o) => (
                <option key={o.seconds} value={o.seconds}>
                  Expires in {o.label}
                </option>
              ))}
            </select>
            <button
              id="create-btn"
              ref={createBtnRef}
              className="btn"
              onClick={handleCreate}
              disabled={createLoading || !secret.trim() || !recipientId.trim()}
            >
              {createLoading ? 'Encrypting…' : 'Encrypt & Share'}
            </button>
          </div>
        </div>

        {createResult && (
          <div id="create-result" className="result-card" style={{ marginTop: '1rem' }}>
            <p className="muted" style={{ marginBottom: '0.5rem' }}>Secret share link</p>
            <div className="row" style={{ marginBottom: '0.5rem' }}>
              <input
                id="secret-link-input"
                type="text"
                readOnly
                value={createResult.link}
                className="link-input"
                onClick={(e) => (e.target as HTMLInputElement).select()}
              />
              <button
                id="copy-link-btn"
                ref={copyBtnRef}
                type="button"
                className={`btn${copiedLink ? ' btn-ghost' : ''}`}
                style={{ flexShrink: 0 }}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(createResult.link)
                  } catch {
                    const input = document.getElementById('secret-link-input') as HTMLInputElement
                    if (input) {
                      input.select()
                      document.execCommand('copy')
                    }
                  }
                  setCopiedLink(true)
                  triggerBounce(copyBtnRef.current)
                  setTimeout(() => setCopiedLink(false), 2000)
                }}
              >
                {copiedLink ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <hr className="divider" style={{ margin: '0.6rem 0' }} />
            <p className="muted" style={{ marginBottom: '0.25rem' }}>Payload ID</p>
            <code id="secret-payload-id" style={{ wordBreak: 'break-all', display: 'block', marginBottom: '0.35rem' }}>
              {createResult.id}
            </code>
            <p className="muted">Expires {createResult.expiresAt}</p>
          </div>
        )}

        {createError && (
          <p className="error-box" style={{ marginTop: '0.75rem' }}>{createError}</p>
        )}
      </section>

      {/* ── Retrieve Secret ── */}
      <section className="glass" style={{ borderRadius: '16px', padding: '1.25rem' }}>
        <h2>Retrieve Secret</h2>
        <div className="row">
          <input
            type="text"
            value={payloadId}
            onChange={(e) => setPayloadId(e.target.value)}
            placeholder="Payload ID"
            style={{ flex: 1 }}
          />
          <button
            id="retrieve-btn"
            ref={retrieveBtnRef}
            className="btn"
            onClick={() => handlePreRevealCheck()}
            disabled={retrieveLoading || !payloadId.trim()}
            onPointerUp={(e) => {
              if (!retrieveLoading && payloadId.trim()) triggerBounce(e.currentTarget)
            }}
          >
            {retrieveLoading ? 'Verifying…' : 'Reveal Secret'}
          </button>
        </div>

        {retrieveResult && (
          <div id="retrieve-result" className="result-card" style={{ marginTop: '0.75rem' }}>
            <p className="status-ok" style={{ marginBottom: '0.5rem' }}>&#x2713; Decrypted secret plaintext</p>
            <pre style={{ margin: 0 }}>{retrieveResult}</pre>
          </div>
        )}

        {retrieveError && (
          <p className="error-box" style={{ marginTop: '0.75rem' }}>{retrieveError}</p>
        )}
      </section>

      {/* ── Burn-After-Reading Modal ── */}
      {showConfirmModal && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h3 style={{ color: 'var(--danger)', marginBottom: '0.75rem' }}>
              Burn-After-Reading Warning
            </h3>
            <p style={{ color: 'var(--fg-dim)', lineHeight: 1.6, marginBottom: '1rem' }}>
              This secret is stored ephemerally. Revealing it will{' '}
              <strong style={{ color: 'var(--fg)' }}>permanently and irreversibly destroy</strong>{' '}
              it from the server.
            </p>

            {status === 'authenticated' && username ? (
              <div className="row-end" style={{ marginTop: '1.25rem' }}>
                <button
                  id="cancel-reveal-btn"
                  className="btn btn-ghost"
                  onClick={() => setShowConfirmModal(false)}
                  onPointerUp={(e) => triggerBounce(e.currentTarget)}
                >
                  Cancel
                </button>
                <button
                  id="confirm-reveal-btn"
                  className="btn btn-danger"
                  onClick={handleConfirmReveal}
                  onPointerUp={(e) => triggerBounce(e.currentTarget)}
                >
                  Reveal &amp; Burn
                </button>
              </div>
            ) : (
              <>
                <p className="muted" style={{ marginBottom: '1rem' }}>
                  Log in as the intended recipient to decrypt and access this secret.
                </p>
                <div className="row-end">
                  <button
                    id="cancel-reveal-btn"
                    className="btn btn-ghost"
                    onClick={() => setShowConfirmModal(false)}
                    onPointerUp={(e) => triggerBounce(e.currentTarget)}
                  >
                    Cancel
                  </button>
                  <button
                    id="modal-login-btn"
                    className="btn"
                    onClick={handleLogin}
                    onPointerUp={(e) => triggerBounce(e.currentTarget)}
                  >
                    Login to Reveal
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </main>
  )
}
