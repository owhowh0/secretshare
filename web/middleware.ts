import { NextResponse, type NextRequest } from 'next/server'

// Next.js emits its React Server Component payload as inline <script> blocks in
// every HTML response. Under script-src 'self' the browser refuses them and the
// page never hydrates, so a nonce is the only way to keep scripts strict without
// falling back to 'unsafe-inline' — which would defeat the point, since an
// injected script reading plaintext before encryption is the threat CLAUDE.md
// §13 names CSP against.
//
// The nonce must be unique per response, so it cannot come from the static
// headers() table in next.config.ts; it is generated here and Next copies it
// onto its own inline scripts when it sees one in the request's CSP header.
//
// Every origin the app talks to — the API under /api, Keycloak under /keycloak —
// is proxied by Traefik onto this same host, so 'self' is the whole allowlist.
// Keycloak login is a top-level redirect, covered by form-action 'self'.
//
// HSTS is deliberately absent: it belongs to the TLS edge (CLAUDE.md §5), and
// sending it over plain HTTP in development would poison the browser's HSTS
// cache for localhost.

const isDev = process.env.NODE_ENV !== 'production'

function buildCsp(nonce: string): string {
  return [
    "default-src 'self'",
    // 'strict-dynamic' lets the nonced bootstrap load the chunks it needs while
    // keeping any injected <script> without the nonce blocked. 'unsafe-eval' is
    // required by the dev server's hot reload only and is never sent in
    // production.
    isDev
      ? `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' 'unsafe-eval'`
      : `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    // 'unsafe-inline' is a known weakening, confined to styles. React renders
    // inline style={{…}} props as style attributes and Next inlines the
    // stylesheet into a <style> block; neither can carry a nonce. Scripts are
    // the XSS-to-key-theft path and stay strict regardless.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    // No plugins, and no framing by anyone: clickjacking a one-time reveal would
    // burn the secret on the attacker's behalf.
    "object-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
    "form-action 'self'",
  ].join('; ')
}

export function middleware(request: NextRequest) {
  const nonce = crypto.randomUUID().replaceAll('-', '')
  const csp = buildCsp(nonce)

  // Next reads the nonce back off the request's CSP header to stamp its own
  // inline scripts, so the header has to be set on the request as well as the
  // response.
  const requestHeaders = new Headers(request.headers)
  requestHeaders.set('x-nonce', nonce)
  requestHeaders.set('Content-Security-Policy', csp)

  const response = NextResponse.next({ request: { headers: requestHeaders } })
  response.headers.set('Content-Security-Policy', csp)
  return response
}

export const config = {
  matcher: [
    '/',
    {
      source: '/((?!_next/static|_next/image|favicon.ico).*)',
      missing: [
        { type: 'header', key: 'next-router-prefetch' },
        { type: 'header', key: 'purpose', value: 'prefetch' },
      ],
    },
  ],
}
