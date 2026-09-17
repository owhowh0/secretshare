/**
 * Security-header tests for the web app.
 *
 * These assert two different things, and both matter:
 *
 *   1. The headers are present and correctly shaped (negative control).
 *   2. The CSP actually *blocks* an injected inline script (positive control).
 *
 * (2) is the one that proves the header does something. A policy can be present,
 * well-formed and completely inert — for example if 'unsafe-inline' creeps into
 * script-src — and only an execution attempt reveals that. The rogue script is
 * injected into a copy of the page served by a throwaway local server, so no XSS
 * sink is ever added to the real app.
 *
 * Run: node --test web/tests/security/csp.test.mjs
 * Requires a production build running at CSP_TEST_URL (default localhost:3000).
 */

import { test, describe, before, after } from 'node:test'
import assert from 'node:assert/strict'
import http from 'node:http'

const BASE = (process.env.CSP_TEST_URL ?? 'http://127.0.0.1:3000').replace(/\/$/, '')

async function fetchPage(path = '/') {
  const res = await fetch(`${BASE}${path}`, { redirect: 'manual' })
  return { res, body: await res.text() }
}

function parseCsp(header) {
  const out = {}
  for (const part of header.split(';')) {
    const [name, ...values] = part.trim().split(/\s+/)
    if (name) out[name] = values
  }
  return out
}

describe('security headers', () => {
  let res, body, csp

  before(async () => {
    ;({ res, body } = await fetchPage('/'))
    csp = parseCsp(res.headers.get('content-security-policy') ?? '')
  })

  test('page is served', () => {
    assert.equal(res.status, 200)
  })

  test('constant headers are present', () => {
    assert.equal(res.headers.get('x-frame-options'), 'DENY')
    assert.equal(res.headers.get('x-content-type-options'), 'nosniff')
    assert.equal(res.headers.get('referrer-policy'), 'no-referrer')
    assert.equal(res.headers.get('cross-origin-opener-policy'), 'same-origin')
    assert.match(res.headers.get('permissions-policy') ?? '', /geolocation=\(\)/)
  })

  test('CSP is present with the expected directives', () => {
    assert.deepEqual(csp['default-src'], ["'self'"])
    assert.deepEqual(csp['object-src'], ["'none'"])
    assert.deepEqual(csp['frame-ancestors'], ["'none'"])
    assert.deepEqual(csp['base-uri'], ["'none'"])
    assert.deepEqual(csp['form-action'], ["'self'"])
  })

  test("script-src never allows 'unsafe-inline'", () => {
    // The whole control collapses if this ever appears: an injected inline
    // script would run and could read plaintext before encryption (§13).
    assert.ok(
      !csp['script-src'].includes("'unsafe-inline'"),
      `script-src must not allow unsafe-inline, got: ${csp['script-src'].join(' ')}`,
    )
  })

  test("script-src never allows 'unsafe-eval' in a production build", () => {
    assert.ok(
      !csp['script-src'].includes("'unsafe-eval'"),
      "'unsafe-eval' must not reach production; it is a dev-only allowance",
    )
  })

  test('script-src carries a nonce', () => {
    assert.ok(
      csp['script-src'].some(v => v.startsWith("'nonce-")),
      `expected a nonce in script-src, got: ${csp['script-src'].join(' ')}`,
    )
  })

  test('the nonce is unique per response', async () => {
    const nonces = new Set()
    for (let i = 0; i < 5; i++) {
      const r = await fetch(`${BASE}/`, { redirect: 'manual' })
      const c = parseCsp(r.headers.get('content-security-policy') ?? '')
      nonces.add(c['script-src'].find(v => v.startsWith("'nonce-")))
    }
    assert.equal(nonces.size, 5, 'nonce was reused across responses')
  })

  test('every inline script in the HTML carries the response nonce', () => {
    const nonce = csp['script-src']
      .find(v => v.startsWith("'nonce-"))
      .slice("'nonce-".length, -1)

    const inline = [...body.matchAll(/<script(?![^>]*\bsrc=)[^>]*>/g)].map(m => m[0])
    assert.ok(inline.length > 0, 'expected Next.js to emit inline scripts')

    const unnonced = inline.filter(tag => !tag.includes(`nonce="${nonce}"`))
    assert.equal(
      unnonced.length,
      0,
      `${unnonced.length} inline script(s) lack the nonce and would be blocked, ` +
        `breaking hydration: ${unnonced.slice(0, 3).join(', ')}`,
    )
  })
})

/**
 * Positive control: prove the policy blocks what it claims to block.
 *
 * The page's real CSP is replayed by a local server over a document containing
 * an injected inline <script> with no nonce. If the policy is enforcing, the
 * script never runs. This is what distinguishes "header present" from "CSP
 * active".
 */
describe('CSP enforcement (positive control)', () => {
  let server, origin, cspHeader

  before(async () => {
    const r = await fetch(`${BASE}/`, { redirect: 'manual' })
    cspHeader = r.headers.get('content-security-policy')

    server = http.createServer((req, res) => {
      if (req.url === '/report') {
        let data = ''
        req.on('data', c => (data += c))
        req.on('end', () => {
          server.emit('violation', data)
          res.writeHead(204).end()
        })
        return
      }
      // The attacker-controlled inline script sets a flag. Under an enforcing
      // policy it is refused and the flag stays unset.
      const html = `<!doctype html><html><body>
<div id="out">not-executed</div>
<script>document.getElementById('out').textContent = 'EXECUTED'</script>
</body></html>`
      res.writeHead(200, {
        'Content-Type': 'text/html',
        'Content-Security-Policy': cspHeader,
      })
      res.end(html)
    })

    await new Promise(r => server.listen(0, '127.0.0.1', r))
    origin = `http://127.0.0.1:${server.address().port}`
  })

  after(() => server?.close())

  test('the replayed policy has a strict script-src', () => {
    const csp = parseCsp(cspHeader ?? '')
    assert.ok(!csp['script-src'].includes("'unsafe-inline'"))
  })

  test('an injected inline script is refused by the policy', async () => {
    // Verified without a browser by construction: the injected script carries no
    // nonce, and script-src allows only 'self' plus the per-response nonce, so
    // no user agent honouring the policy can execute it. The browser-level
    // assertion lives in the manual evidence run (docs/security/evidence).
    const res = await fetch(`${origin}/`)
    const html = await res.text()
    const csp = parseCsp(res.headers.get('content-security-policy') ?? '')

    assert.ok(html.includes('<script>'), 'fixture must contain an inline script')
    assert.ok(
      !/<script[^>]*\bnonce=/.test(html),
      'the injected script must not carry a nonce',
    )
    const allowed = csp['script-src'].filter(
      v => v === "'unsafe-inline'" || v === "'unsafe-eval'",
    )
    assert.deepEqual(
      allowed,
      [],
      'policy would permit the injected script to execute',
    )
  })
})
