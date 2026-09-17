import type { NextConfig } from 'next'

// The Content-Security-Policy is deliberately not here: it carries a per-request
// nonce and is set in middleware.ts. Two CSP headers on one response would be
// intersected by the browser, so this table holds only the constant headers.
//
// HSTS is deliberately absent: it belongs to the TLS edge (CLAUDE.md §5), and
// sending it over plain HTTP in development would poison the browser's HSTS
// cache for localhost.
const securityHeaders = [
  // Redundant with the CSP's frame-ancestors for current browsers, kept for
  // older ones: clickjacking a one-time reveal would burn the secret on the
  // attacker's behalf.
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  // A payload id in the URL must never leak to a third party (invariant 6).
  { key: 'Referrer-Policy', value: 'no-referrer' },
  { key: 'Permissions-Policy', value: 'geolocation=(), microphone=(), camera=()' },
  { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
]

const nextConfig: NextConfig = {
  basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? '',
  trailingSlash: true,
  output: 'standalone',
  async headers() {
    return [
      {
        // Applied to every route, so a new page cannot forget them.
        source: '/:path*',
        headers: securityHeaders,
      },
    ]
  },
}

export default nextConfig
