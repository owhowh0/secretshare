# Security controls — web application

Each row states the security problem, why it matters for SecretShare specifically,
how it is implemented, how it was tested, and what it does **not** cover.

API-side controls (audit logging, authentication errors) are documented in
`api/docs/security/security-controls.md`.

---

## Web response headers

### WEB-1 — The page that performs encryption had no Content Security Policy

| | |
|---|---|
| **Security problem** | The Next.js app shipped with no CSP, no `X-Frame-Options`, and no `X-Content-Type-Options`. Any injected script — through a dependency compromise, a stored XSS, or a malicious build artifact — would execute with full access to the page. The API already sets strict headers (`api/app/core/headers.py`), but those apply to JSON responses and do nothing for the document that runs the code. |
| **Relevance** | CLAUDE.md §13 names strict CSP as the primary mitigation for the project's central acknowledged weakness: the relay serves the JavaScript that performs encryption, so a compromised server can ship key-stealing code. Once browser crypto lands, an injected script reads plaintext *before* encryption, defeating invariant 1 without ever touching the server's stored ciphertext. CSP is what raises the cost of that attack. |
| **Implementation** | `web/middleware.ts` sets a per-request CSP; `web/next.config.ts` sets the constant headers on every route. Policy: `default-src 'self'`, `script-src 'self' 'nonce-<per-request>' 'strict-dynamic'`, `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'none'`, `form-action 'self'`, plus `img-src`, `font-src`, `connect-src` pinned to `'self'`. Constant headers: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, `Cross-Origin-Opener-Policy: same-origin`. Every origin the app uses — the API under `/api`, Keycloak under `/keycloak` — is proxied onto the same host by Traefik, so `'self'` is the complete allowlist. |
| **How tested** | `web/tests/security/csp.test.mjs` — 10 tests, no test dependencies (Node's built-in runner). **Negative control:** all headers present and correctly shaped; `script-src` never contains `'unsafe-inline'` or `'unsafe-eval'`; the nonce is unique across 5 consecutive responses; every inline `<script>` in the HTML carries the response's nonce. **Positive control:** the app's real policy is replayed over a document containing an injected, un-nonced inline script. In a headless Chromium run the script did **not** execute (`#out` stayed `not-executed`), a `securitypolicyviolation` event fired (`script-src-elem blocked inline`), and the browser logged *"Executing inline script violates the following Content Security Policy directive… The action has been blocked."* The same run confirms the real app still hydrates with zero violations and zero page errors. Verified end-to-end through Traefik on `http://localhost` against the production `bun` Docker image, not only a local dev build. Evidence in `docs/security/evidence/`. |
| **Limitations** | **`style-src` still requires `'unsafe-inline'`.** React renders the inline `style={{…}}` props in `app/page.tsx` as style attributes and Next.js inlines its stylesheet into a `<style>` block; neither can carry a nonce. This permits CSS-based attacks (data exfiltration via attribute selectors, UI redressing within the page) and must be closed by moving those styles into `globals.css`. Scripts — the XSS-to-key-theft path — remain strict. **No SRI**, pending hashed asset names. **No HSTS**, which belongs at the TLS edge (CLAUDE.md §5) and is absent by design in a plain-HTTP dev stack. **No `report-uri`/`report-to`**, so violations in production are invisible to operators. The nonce forces `dynamic = 'force-dynamic'` in `app/layout.tsx`, giving up static prerendering: a prerendered page would be served from the build cache with a stale nonce and every script on it would be blocked. `'strict-dynamic'` means any script the nonced bootstrap loads is trusted transitively, so a compromised dependency already inside the bundle is **not** mitigated by this control — SRI and dependency review are what address that. |

---

## Open finding

### WEB-2 — Keycloak login is broken by an incorrect `redirect_uri` (pre-existing)

**Status: open. Found while testing WEB-1. Not caused by, and not fixed on, the CSP branch.**

| | |
|---|---|
| **Security problem** | Clicking "Login with Keycloak" never reaches Keycloak. NextAuth advertises `signinUrl: http://0.0.0.0:3000/api/auth/signin/keycloak` and issues an authorization request with `redirect_uri=http%3A%2F%2F0.0.0.0%3A3000%2Fapi%2Fauth%2Fcallback%2Fkeycloak`. `0.0.0.0` is the container's bind address, not the browser-facing origin. |
| **Relevance** | Authentication is unusable in the compose stack, so no authenticated flow can currently be demonstrated or security-tested end to end. A `redirect_uri` that does not match what Keycloak has registered is also the field that OAuth redirect-hijacking attacks target, so it should be pinned deliberately rather than inferred. |
| **Evidence that it is not the CSP** | The server-side redirect resolves correctly to `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth?…`, so `form-action 'self'` is not blocking it, and **no CSP violation is raised**. Confirmed by rebuilding the `web` image from `main` — with no CSP header present at all — and reproducing the identical failure: `reached Keycloak: false`. |
| **Cause** | `AUTH_TRUST_HOST=true` combined with an unset `AUTH_URL`/`NEXTAUTH_URL` lets NextAuth derive the public origin from the listening socket. |
| **Possible fixes** | Set `AUTH_URL=http://localhost` (or the deployed origin) in the `web` service environment, and ensure Traefik forwards `X-Forwarded-Host`/`X-Forwarded-Proto`. Needs a team decision on the canonical public origin per environment, so it is recorded here rather than patched silently on a CSP branch. |
