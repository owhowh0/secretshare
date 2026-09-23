# Security controls — web application

Each row states the security problem, why it matters for SecretShare specifically,
how it is implemented, how it was tested, and what it does **not** cover.

API-side controls (AUD, AUTH, SEC, API, TLS, DB) are documented in
`api/docs/security/security-controls.md`. Requirement, threat and risk identifiers
refer to `security-requirements.md`, `threat-model.md` and `risk-register.md` in
`api/docs/security/`.

| ID | Control | Requirement | Status |
|---|---|---|---|
| WEB-1 | Content Security Policy and response headers | SR-10, SR-28 | Implemented |
| WEB-2 | Keycloak `redirect_uri` derived from the bind address | SR-03 | Closed finding |
| WEB-3 | Browser-side hybrid encryption | SR-01, SR-16 | Implemented |
| WEB-4 | Non-destructive link opening and confirmed reveal | SR-19 | Implemented |
| WEB-5 | Session cookies, CSRF and session lifetime | SR-11, SR-12, SR-14 | Partial |

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

## Findings

### WEB-2 — Keycloak login is broken by an incorrect `redirect_uri` (pre-existing)

**Status: closed on 17 September 2026 by commit `bf496be` ("inject AUTH_URL and
align Keycloak issuer in compose").** The finding is kept for its record of cause
and verification.

| | |
|---|---|
| **Security problem** | Clicking "Login with Keycloak" never reached Keycloak. NextAuth advertised `signinUrl: http://0.0.0.0:3000/api/auth/signin/keycloak` and issued an authorization request with `redirect_uri=http%3A%2F%2F0.0.0.0%3A3000%2Fapi%2Fauth%2Fcallback%2Fkeycloak`. `0.0.0.0` is the container's bind address, not the browser-facing origin. |
| **Relevance** | Authentication was unusable in the compose stack, so no authenticated flow could be demonstrated or tested end to end. A `redirect_uri` that is inferred rather than configured is the parameter that OAuth redirect attacks target, so it should be pinned deliberately. |
| **Evidence that it was not the CSP** | The server-side redirect resolved to `http://localhost/keycloak/realms/secretshare/protocol/openid-connect/auth?…`, so `form-action 'self'` did not block it, and no CSP violation was raised. The failure reproduced identically on an image built from `main` without any CSP header. |
| **Cause** | `AUTH_TRUST_HOST=true` combined with an unset `AUTH_URL` let NextAuth derive the public origin from the listening socket. |
| **Resolution** | Both compose files set `AUTH_URL` to the public origin: `http://localhost:${TRAEFIK_WEB_PORT}/api/auth` in `docker-compose.yml` and `https://${PR_HOSTNAME}/api/auth` in `docker-compose.preview.yml`. Traefik routes `/api/auth` to the web service with priority 150, above the API router. |
| **Limitations** | `AUTH_TRUST_HOST=true` remains set, so Auth.js still accepts forwarded host headers where `AUTH_URL` is absent. No automated browser test covers the sign-in redirect; closure rests on the configuration and manual testing. The Keycloak client accepts redirect URIs for `http://localhost:*/*`, `http://127.0.0.1:*/*` and `https://*.ts.net/*`, which is wider than the deployed origins (R-15). |

---

## Client-side cryptography

### WEB-3 — Browser-side hybrid encryption

| | |
|---|---|
| **Security problem** | When a secret is encrypted on the server, the operator, the hosting provider and anyone who compromises the server can read it. |
| **Relevance** | Requirement NFR-01 and invariant 1: the relay must be able to store and forward a secret without being able to read it. This is the property that distinguishes SecretShare from server-side one-time-secret services. |
| **Implementation** | `web/lib/crypto.ts` uses only the Web Cryptography API (`window.crypto.subtle`). For each secret the browser draws a 256-bit content key and a 96-bit IV with `crypto.getRandomValues`, encrypts with AES-GCM (128-bit tag), and wraps the content key with RSA-OAEP (SHA-256) for every active device key of the recipient returned by `GET /api/keys/{user_id}`. Each device key pair (RSA-OAEP, 2048-bit modulus, exponent 65537) is generated on first sign-in by `web/lib/key-store.ts`, stored as `CryptoKey` objects in IndexedDB (`secretshare_keystore`, store `device_keys`, keyed by user name), and its public half is registered through `POST /api/keys/register` in SPKI PEM form. On reveal, the browser tries each wrapped key with its private key and decrypts in memory. The format is specified in `api/docs/architecture/crypto-spec.md`. |
| **How tested** | **No automated test covers `web/lib/crypto.ts`.** The server side of the property is tested: `tests/test_secrets.py::TestSecretService::test_create_then_retrieve` asserts the API returns the envelope fields unchanged, and the API schemas accept no plaintext field. |
| **Limitations** | **Device private keys are generated with `extractable: true`** (`generateRsaKeyPair`), so a script running in the origin can export them (R-02). This contradicts the design, which requires non-exportable keys. Clearing browser data deletes the key, and secrets pending for it become unreadable. Registering a key revokes the user's previous key of the same platform, so only the most recent browser can decrypt new secrets. Envelopes are not signed, so the recipient cannot verify the sender (R-07), and public keys are not verified by fingerprint (R-08). The code performing encryption is served by the relay (R-01). |

---

## Reveal flow

### WEB-4 — Non-destructive link opening and confirmed reveal

| | |
|---|---|
| **Security problem** | If opening a link is enough to consume a secret, automated clients that fetch links destroy it or keep a copy: chat unfurlers, mail link scanners, browser prefetch. A framed page can trick a user into clicking a destructive button (clickjacking). |
| **Relevance** | Share links are meant to be pasted into Slack, Teams and mail, where unfurlers and scanners fetch every URL. |
| **Implementation** | `web/app/page.tsx`. A link of the form `/?id=<id>`, `/#<id>`, `/s/<id>` or `/secret/<id>` only triggers `POST /api/secrets/exists` with the identifier in the body. If the secret exists, a modal states that revealing will destroy it. `POST /api/secrets/reveal` is sent only after the user confirms, and it requires the recipient's bearer token (AUTH-3); an anonymous visitor is sent to Keycloak first. The page is a client component, so a fetcher that does not run JavaScript triggers no API call. Framing is refused by `frame-ancestors 'none'` and `X-Frame-Options: DENY` (WEB-1). After a successful reveal the identifier is removed from the address bar with `history.replaceState`. |
| **How tested** | `api/tests/test_secrets.py::test_check_exists_does_not_consume_the_secret`. The preview smoke test (`.github/scripts/test_secret_lifecycle.sh`) checks that the secret still exists after a denied reveal. `web/tests/security/csp.test.mjs` asserts the anti-framing headers. No browser test covers the modal sequence. |
| **Limitations** | The identifier is in the query string or path of the page request, so it reaches the web tier and the browser history before the page script runs (R-04). `replaceState` runs only after a successful reveal; after a cancelled or failed reveal the identifier stays in the address bar. `POST /secrets/exists` is unauthenticated, so any holder of a link can confirm that the secret exists (accepted in `threat-model.md`, section 9). |

---

## Session management

### WEB-5 — Session cookies, CSRF and session lifetime

| | |
|---|---|
| **Security problem** | Session cookies readable by scripts can be stolen through XSS; cookies sent on cross-site requests enable cross-site request forgery; sessions without a bounded lifetime or a complete logout extend the period in which a stolen session is usable. |
| **Relevance** | Brief §3 requires anti-CSRF protection and `HttpOnly`, `Secure` and `SameSite` cookies; brief §4 requires session timeout and invalidation. The session carries the token that authorises a reveal. |
| **Implementation** | Auth.js (`next-auth` 5.0.0-beta.32), configured in `web/auth.ts` with the Keycloak provider and no database adapter, so the session is a JWT stored in an encrypted cookie keyed from `AUTH_SECRET`. Cookie attributes are the Auth.js defaults: `HttpOnly`, `SameSite=Lax`, `Path=/`, and `Secure` with the `__Secure-` / `__Host-` prefixes when the origin is HTTPS. Auth.js protects its own sign-in and sign-out `POST` endpoints with a double-submit CSRF token. **The API does not use cookies**: the client sends the access token in the `Authorization` header (`getHeaders` in `page.tsx`), which a browser never attaches to a cross-site request, so forged requests reach the API unauthenticated. Keycloak access tokens expire after the realm default of 5 minutes. |
| **How tested** | **No automated test covers cookie attributes, CSRF handling or session lifetime.** `api/tests/test_frontend_and_routing.py::TestFrontendAssets::test_auth_js_module_configured_with_keycloak` only asserts that the provider is configured. |
| **Limitations** | The `session` callback copies the access token into the session object, which `useSession` exposes to JavaScript; an injected script can read it (R-02). The Auth.js session lifetime is the default of 30 days, while the access token is not refreshed. `signOut` clears the Auth.js cookie only; the Keycloak SSO session remains, so the next sign-in completes without credentials (R-17). Local compose runs over HTTP, so cookies there lack `Secure`. `docker-compose.yml` falls back to a published `AUTH_SECRET` when the variable is unset (R-20). None of the attributes is configured explicitly. |
