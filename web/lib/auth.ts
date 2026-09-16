import { randomString, sha256Challenge } from './pkce'

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? ''
const KEYCLOAK = `${BASE_PATH}/keycloak`
const REALM = 'secretshare'
const CLIENT_ID = 'secretshare-api'

export function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = sessionStorage.getItem('token')
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

export async function startLogin(): Promise<void> {
  const verifier = randomString()
  sessionStorage.setItem('verifier', verifier)
  const challenge = await sha256Challenge(verifier)

  const redirectUri = window.location.origin + (BASE_PATH ? BASE_PATH + '/' : '/')
  sessionStorage.setItem('redirectUri', redirectUri)

  const authUrl = new URL(
    `${window.location.origin}${KEYCLOAK}/realms/${REALM}/protocol/openid-connect/auth`
  )
  authUrl.searchParams.set('client_id', CLIENT_ID)
  authUrl.searchParams.set('response_type', 'code')
  authUrl.searchParams.set('scope', 'openid profile email')
  authUrl.searchParams.set('redirect_uri', redirectUri)
  authUrl.searchParams.set('code_challenge', challenge)
  authUrl.searchParams.set('code_challenge_method', 'S256')

  window.location.href = authUrl.toString()
}

export async function handleCallback(): Promise<void> {
  const params = new URLSearchParams(window.location.search)
  const code = params.get('code')
  if (!code) return

  const verifier = sessionStorage.getItem('verifier')
  const redirectUri =
    sessionStorage.getItem('redirectUri') ??
    window.location.origin + (BASE_PATH ? BASE_PATH + '/' : '/')

  window.history.replaceState({}, document.title, window.location.pathname)

  if (!verifier) return

  const res = await fetch(`${KEYCLOAK}/realms/${REALM}/protocol/openid-connect/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: CLIENT_ID,
      code,
      redirect_uri: redirectUri,
      code_verifier: verifier,
    }).toString(),
  })

  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`Token exchange failed (HTTP ${res.status}): ${body}`)
  }

  const data = await res.json()
  sessionStorage.setItem('token', data.access_token)
  sessionStorage.removeItem('verifier')
}

export async function fetchUser(
  apiBase: string
): Promise<{ preferred_username?: string; sub?: string } | null> {
  const token = sessionStorage.getItem('token')
  if (!token) return null

  const res = await fetch(`${apiBase}/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })

  if (!res.ok) {
    sessionStorage.removeItem('token')
    return null
  }

  return res.json()
}

export function logout(): void {
  sessionStorage.removeItem('token')
}
