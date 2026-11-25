# OWASP ZAP scan report: SecretShare

| | |
|---|---|
| Date | 25 November 2026 |
| Tool | OWASP ZAP 2.17.0 (daemon mode, driven through its API) |
| Target | SecretShare dev stack on `http://localhost` (Traefik → Next.js web, FastAPI API, Keycloak) |
| Branch | `security/zap-scan` |
| Raw evidence | [`evidence/zap/before/`](evidence/zap/before/) and [`evidence/zap/after/`](evidence/zap/after/): HTML, JSON and Markdown reports from ZAP; [`evidence/zap/screenshots/`](evidence/zap/screenshots/) |

## Summary

ZAP found **no SQL injection, no cross-site scripting and no command or template
injection** in SecretShare. It sent 576 SQL injection payloads, 152 reflected XSS
payloads and 1,990 DOM XSS checks.

It did find **seven real problems** in our own code and configuration, Z-01 to Z-07
below. One of them, an unauthenticated public-key lookup that allows user
enumeration (Z-02), was found by reviewing the API endpoints in ZAP's site tree,
not by an automatic alert. ZAP does not detect broken access control by itself.
All seven are fixed in this branch and confirmed by a second scan (section 6).

The remaining alerts are either known, documented trade-offs (Z-08, Z-09),
false positives (Z-10, Z-11), or come from Keycloak, the third-party identity
provider (section 7).

| Risk | Before: alert types in our code | After: alert types in our code |
|---|---|---|
| High | 1 (false positive, Z-11) | 1 (same false positive) |
| Medium | 6 | 5 (Swagger UI in dev only, plain HTTP locally, style CSP: all accepted) |
| Low | 4 | 2 (Swagger UI in dev only, NextAuth error page) |
| Informational | 4 | 4 |

## 1. What OWASP ZAP is

OWASP ZAP (Zed Attack Proxy) is an open-source web application security scanner.
It sits between the browser and the application as an intercepting proxy, so it
sees every request and response, and it can also send its own attack requests.

- **Passive scan.** ZAP inspects the traffic that flows through it without
  changing or sending anything. It flags missing security headers, insecure
  cookies, information leaks and error pages. Passive scanning is safe to run
  against any system, because it only reads.
- **Active scan.** ZAP replays every request it knows about, replacing each
  parameter, header and body field with attack payloads: SQL injection, XSS,
  path traversal, command injection, template injection and more. It then
  judges from the responses whether an attack worked. Active scanning changes
  data and sends thousands of requests, so it must only be run against systems
  you own or are authorised to test, never against production.
- **Spiders.** The classic spider follows links in HTML. The AJAX spider drives
  a real browser so that JavaScript-built pages, like our Next.js app, are
  discovered too.

## 2. Environment setup

1. **Application.** Started the development stack:
   `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build`.
   Everything is served on `http://localhost` through Traefik: the web app at `/`,
   the API at `/api`, and Keycloak at `/keycloak`.
2. **ZAP as a proxy.** Started ZAP headless on `127.0.0.1:8090` with a random API key:
   `/usr/share/zaproxy/zap.sh -daemon -host 127.0.0.1 -port 8090 -config api.key=<random>`.
   On Arch, the `/usr/bin/zaproxy` wrapper drops all arguments, so `zap.sh` has
   to be called directly.
3. **Browser through ZAP.** The browser was configured to use `127.0.0.1:8090` as
   its HTTP proxy. Two things are needed for this to work:
   - Chromium bypasses proxies for `localhost` by default, so it was started
     with `--proxy-bypass-list=<-loopback>`.
   - In Firefox, set Settings → Network Settings → Manual proxy to
     `127.0.0.1:8090` and `network.proxy.allow_hijacking_localhost = true` in
     `about:config`.
   - For HTTPS targets, ZAP's root CA, from Tools → Options → Network →
     Server Certificates, must be imported into the browser. Our local stack
     is plain HTTP, so this step was not needed.
4. **Reachability check.** `curl -x http://127.0.0.1:8090 http://localhost/api/health`
   returned `200`, and the request appeared in ZAP's history.
5. **Scope.** A ZAP context `secretshare` was created with `http://localhost.*`.
   Keycloak (`/keycloak/*`) was **excluded from the active scan**: it is a
   third-party product we do not maintain, and attacking it would only test
   Keycloak, not our code. It was still passively analysed.

## 3. Performing the scan

### 3.1 Passive scan

The browser was driven through the proxy along the full user journey, scripted with
Playwright so it can be repeated exactly:

1. open the home page ([screenshot](evidence/zap/screenshots/01-home.png));
2. log in through Keycloak as `testuser` ([screenshot](evidence/zap/screenshots/02-keycloak-login.png));
3. the app generates a device key pair and registers the public key;
4. create an encrypted secret for `testuser` ([screenshot](evidence/zap/screenshots/03-secret-created.png));
5. open the share link, confirm the burn warning, reveal ([screenshots](evidence/zap/screenshots/04-burn-warning.png), [revealed](evidence/zap/screenshots/05-revealed.png));
6. open the same link again, which is rejected because the secret is burned ([screenshot](evidence/zap/screenshots/06-burned.png));
7. visit the error routes, `/api/docs` and `/api/health`, then log out.

ZAP then added to its site tree with:

- the **OpenAPI import** of `/api/openapi.json`, which gives ZAP every API
  endpoint with example bodies, including endpoints the UI never calls;
- the **classic spider**, which found 128 URLs;
- the **AJAX spider** in headless Chromium, which found 140 resources.

Result: 0 High, 66 Medium, 24 Low and 87 Informational alert instances,
most of them on Keycloak pages
([report](evidence/zap/before/zap-passive-report.html)).

### 3.2 Active scan

- **Policy.** Default policy with all rules, 4 threads. That covers SQL injection
  (generic plus time-based for PostgreSQL, MySQL, MSSQL, Oracle and HSQL), XSS
  (reflected, persistent, DOM), path traversal, remote file inclusion, OS command
  injection, SSTI, SSI, code injection, external redirect, Shellshock and
  React2Shell.
- **Authentication.** The secret, key and `/me` endpoints require a Keycloak
  token. A ZAP *Replacer* rule added `Authorization: Bearer <token>` to every
  `/api/` request. The token was fetched from Keycloak for `testuser` and
  refreshed every 4 minutes, because access tokens live 5 minutes. Without this,
  every authenticated endpoint would only ever have returned 401.
- **Monitoring.** Progress was followed in ZAP's active scan view (`ascan/view/scanProgress`).
  The scan sent about 5,000 requests in 21 minutes.
- **Observation: rate limiting.** 2,728 of the roughly 2,900 attack requests
  against `POST /api/secrets` were answered `429 Too Many Requests` by our rate
  limiter (control API-3). That shows the limiter works, but it also means most
  injection payloads never reached the handler. The re-scan (section 6)
  therefore ran with the limits lifted through a scan-only Compose override,
  so the code behind the limiter was tested too.

Result: [active scan report](evidence/zap/before/zap-active-report.html).

## 4. Findings

Risk is ZAP's rating; *our rating* is adjusted for SecretShare's context where it differs.

### Z-01: Server error on first device-key registration (race condition)

| | |
|---|---|
| ZAP alerts | Application Error Disclosure (90022), Information Disclosure: Debug Error Messages (10023). ZAP rates both Low; our rating is Medium |
| Location | `POST /api/keys/register`: [`api/app/services/keys.py`](../../app/services/keys.py), [`web/app/page.tsx`](../../../web/app/page.tsx) |
| What happened | During the normal login flow the API answered `500 Internal Server Error`. The API log showed `IntegrityError` on `uq_users_platform_user`. |
| Cause | Two problems combined. (1) The frontend's onboarding effect depended on the NextAuth `session` object, which gets a new identity on every session refetch, so it fired **twice in parallel**. (2) `get_or_create_user` does *select, then insert if missing*. Both requests saw no row, both inserted, and the unique constraint rejected the second. The exception was not handled, so it became a 500. |
| Impact | A new user's first login could fail to register their device key, leaving them unable to receive secrets until they reloaded. The response body was generic, so no stack trace leaked, but a reproducible 500 is an availability bug and a signal that attackers probe for. |

### Z-02: Public key directory readable without login (user enumeration / insecure direct object reference)

| | |
|---|---|
| Found by | Manual review of the API endpoints in ZAP's site tree (from the OpenAPI import), then confirmed with a direct unauthenticated request. Not an automatic alert. |
| Risk | Medium |
| Location | `GET /api/keys/{user_id}`: [`api/app/api/routes/keys.py`](../../app/api/routes/keys.py) |
| What happened | Without any token, `GET /api/keys/testuser` returned `200` with the user's device ids, labels and registration timestamps. An unknown name returned `404 "No active device keys found for recipient '<name>'"`. |
| Cause | The route had no authentication dependency. The object (a user's key list) was addressed directly by a guessable identifier, the username, with no access check. This is the "insecure direct object reference" pattern. |
| Impact | Anyone who can reach the server can enumerate which usernames exist and harvest device metadata for targeted phishing. It also contradicts the original API contract, where this endpoint requires a session. |

### Z-03: Swagger UI loads CDN scripts without integrity checks, and needs `unsafe-inline`

| | |
|---|---|
| ZAP alerts | CSP: script-src unsafe-inline (10055), CSP: Failure to Define Directive with No Fallback (10055), Sub Resource Integrity Attribute Missing (90003), Cross-Domain JavaScript Source File Inclusion (10017). Medium / Low |
| Location | `/api/docs`, the FastAPI Swagger UI |
| Cause | FastAPI's built-in Swagger page loads `swagger-ui-bundle.js` from `cdn.jsdelivr.net` with no `integrity` attribute, and needs inline scripts. `DOCS_CSP` in [`headers.py`](../../app/core/headers.py) relaxes the CSP to allow that. |
| Impact | **Higher than ZAP's generic rating suggests.** `/api/docs` is served from the **same origin** as the web app (`localhost`), because Traefik routes both. A compromised or hijacked CDN file would run with full access to that origin, including IndexedDB, **where users' private device keys are stored** (and are currently extractable, R-02). That breaks the zero-knowledge claim. |

### Z-04: Relaxed Swagger CSP applied to any path containing `/docs`

| | |
|---|---|
| Found by | Code review while tracing Z-03 |
| Risk | Low |
| Location | [`api/app/core/headers.py`](../../app/core/headers.py) |
| Cause | `is_docs` matched with a substring test (`"/docs" in request.url.path`), so any future route such as `/secrets/docs` would have got the weak CSP. |
| Impact | Low today, since the API serves only JSON, but a latent weakening that a new route could silently inherit. |

### Z-05: Technology disclosure through `X-Powered-By` and `Server` headers

| | |
|---|---|
| ZAP alert | Server Leaks Information via "X-Powered-By" (10037), Low, 5 pages. `Server: uvicorn` was found manually in the same responses. |
| Location | All web pages (`X-Powered-By: Next.js`) and all API responses (`Server: uvicorn`) |
| Impact | Tells an attacker which frameworks to look up CVEs for. Low on its own, free to remove. |

### Z-06: `favicon.ico` served without a Content-Security-Policy

| | |
|---|---|
| ZAP alert | Content Security Policy (CSP) Header Not Set (10038), Medium |
| Location | `GET /favicon.ico`: [`web/middleware.ts`](../../../web/middleware.ts) |
| Cause | The middleware matcher explicitly excluded `favicon.ico`, so its response (here a 404 page) carried no CSP. |
| Impact | Low. An HTML error response without a CSP is a page where injected markup would not be restricted. |

### Z-07: Site served over plain HTTP

| | |
|---|---|
| ZAP alert | HTTP Only Site (10106), Medium |
| Location | Whole local stack |
| Status | **Accepted for local development.** In preview deployments TLS terminates at the edge (Tailscale Serve). HSTS belongs at that edge too and is tracked as risk R-12. ZAP flags it because this scan ran against the local HTTP stack. |

### Z-08: CSP allows `style-src 'unsafe-inline'`

| | |
|---|---|
| ZAP alert | CSP: style-src unsafe-inline (10055), Medium, 4 pages |
| Status | **Accepted, documented trade-off** ([`middleware.ts`](../../../web/middleware.ts)). React renders `style={{…}}` props as style attributes, which cannot carry a nonce. Scripts, the actual XSS-to-key-theft path, stay strict (`nonce` + `strict-dynamic`). Residual risk is CSS injection, which can deface pages but cannot run code. |

### Z-09: NextAuth error page returns HTTP 500

| | |
|---|---|
| ZAP alert | Application Error Disclosure (90022), Low |
| Location | `GET /api/auth/error?error=Configuration` |
| Cause | ZAP's spider called the OAuth callback `/api/auth/callback/keycloak` without a valid `state`/`code`. NextAuth (Auth.js) rejects it and redirects to its error page, which uses status 500. |
| Status | **Accepted.** This is library behaviour for a forged callback, and the page reveals only the generic word "Configuration", no stack trace or settings. The rejection itself is the correct security outcome. |

### Z-10: Content-Type header missing (false positive)

`/api/auth/csrf`, `/api/auth/providers` and `/api/auth/session` (10019, Informational)
are `308` redirects to the trailing-slash URL (`trailingSlash: true`) with an empty
body. A body-less redirect needs no `Content-Type`.

### Z-11: Path Traversal, High (false positive)

ZAP rated this *High risk, Low confidence*. It changed the `callbackUrl` parameter of
`POST /api/auth/signin/keycloak` to `/keycloak` and saw a different response. That
is a same-origin path, and the response changed only because NextAuth redirected
to it. Auth.js accepts only same-origin callback URLs, and ZAP's own External
Redirect rule (234 requests) found no open redirect. No file is read from disk.

## 5. Remediation

| Finding | Fix | Files |
|---|---|---|
| Z-01 | **Server:** `get_or_create_user` catches `IntegrityError`, rolls back and returns the row the concurrent request created, so a race can no longer produce a 500. **Client:** a `useRef` guard lets only one onboarding run per user; it resets on logout and after a failure so retries still work. | `api/app/services/keys.py`, `web/app/page.tsx` |
| Z-02 | `GET /keys/{user_id}` now requires a valid Keycloak token (`Depends(get_current_user)`), which the web app already sends. The 404 message no longer echoes the requested name. | `api/app/api/routes/keys.py` |
| Z-03 | Swagger UI and `/openapi.json` are **disabled when `ENVIRONMENT=production`** (`docs_url=None`, `openapi_url=None`). They remain in development, where they are useful and the risk is accepted. | `api/app/main.py` |
| Z-04 | `is_docs` uses an exact path set (`DOCS_PATHS`), with the root path stripped first. | `api/app/core/headers.py` |
| Z-05 | `poweredByHeader: false` in Next.js; uvicorn started with `--no-server-header`. | `web/next.config.ts`, `api/Dockerfile` |
| Z-06 | `favicon.ico` removed from the middleware exclusion, so it gets the CSP like every other response. | `web/middleware.ts` |

**Tests added** (`api/tests/`): unauthenticated `GET /keys/{id}` returns 403; the 404
does not echo input; a simulated insert race returns the existing user instead of
raising; the relaxed docs CSP is not applied to `/secrets/docs`. Full suite: 182
passed. Production mode was checked directly: with `ENVIRONMENT=production`,
`docs_url` and `openapi_url` are `None`.

## 6. Re-scan after the fixes

The api and web images were rebuilt with the fixes. Then the whole procedure was
repeated in a fresh ZAP session: the proxied browser journey, the OpenAPI import,
both spiders, and the authenticated active scan. This time a scan-only Compose
override lifted the rate limits, so attack payloads reached the handlers instead
of stopping at 429. Reports: [passive](evidence/zap/after/zap-passive-report.html),
[active](evidence/zap/after/zap-active-report.html).

| Finding | Before | After | How verified |
|---|---|---|---|
| Z-01 race → 500 | 90022 + 10023 on `/api/keys/register` | **gone** | No 500 and no traceback in the API log during the whole re-scan, including 241 successful `201` registrations; new unit test |
| Z-02 key directory without login | `200` for any caller | **`403` without a token** | `curl http://localhost/api/keys/testuser` → 403; new unit test |
| Z-03 Swagger CDN / CSP | 3 alert types on `/api/docs` | still present **in development only** | With `ENVIRONMENT=production`, FastAPI has `docs_url=None`, `openapi_url=None`, so the page does not exist |
| Z-04 docs CSP by substring | latent | **fixed** | New unit test: `/secrets/docs` gets the strict CSP |
| Z-05 `X-Powered-By`, `Server` | 5 pages / all API responses | **gone** | Alert 10037 absent; `curl -I` shows neither header |
| Z-06 favicon without CSP | 10038 | **gone** | Alert 10038 absent |

The rescan with rate limits lifted still found **no SQL injection (618 requests),
reflected XSS (159), OS command injection (532) or template injection (728)**, so
the earlier clean result was not just the rate limiter hiding the handlers. The
browser-based DOM XSS rule did not run in the rescan (0 requests), so DOM XSS
coverage comes from the first scan only (1,990 checks, no alerts).

## 7. Out of scope: Keycloak

Keycloak is a third-party identity provider. Its pages were passively scanned but
not attacked. Its alerts and why they are not ours to fix:

| Alert | Why |
|---|---|
| Cookies without `HttpOnly` (`KC_RESTART`, `KEYCLOAK_SESSION`), `SameSite=None` | Keycloak's session design. `SameSite=None` is needed for OIDC session checks across frames. Over HTTPS, as in production, the cookies also get `Secure`. |
| Absence of anti-CSRF tokens on the login form | Keycloak protects its forms with the one-time `session_code` and `tab_id` in the form URL, which ZAP does not recognise as a CSRF token. |
| CSP wildcard / `unsafe-inline` on login pages | Keycloak's built-in theme. Fixing it means a custom hardened theme, which is planned work, not a code bug in SecretShare. |
| Sensitive information in URL | OAuth authorization codes in redirect URLs are how the protocol works. They are single-use, and PKCE binds them to the client. |

## 8. Conclusions and lessons learned

- **The strong controls held.** No injection of any kind was found. SQLAlchemy
  parameterises every query; the API never renders HTML; the web app's script
  CSP is nonce-based. The rate limiter visibly absorbed the attack traffic.
- **The real bugs were in places a scanner only hints at.** ZAP reported Z-01 as
  a Low "error disclosure". The cause was a concurrency bug spanning the
  frontend and the database, which took log reading to understand. Z-02 produced
  no alert at all. It became visible only because the OpenAPI import put the
  endpoint in front of us, and a human asked whether it should be public.
  Automated scanning finds candidates; judging them needs knowledge of the app.
- **Context changes severity.** ZAP rates a CDN script without SRI as Medium in
  general. For SecretShare, where private keys live in the same origin's
  IndexedDB, it is a path to defeating end-to-end encryption.
- **Authenticated scanning matters.** Without the bearer-token rule, every
  protected endpoint would have returned 401 and been "clean" for the wrong reason.
- **Security controls can hide bugs from scanners.** The rate limiter turned most
  attack requests into 429s. Scanning with the limiter lifted, in a test-only
  configuration, is what tested the code behind it.

### Continuous testing

A one-off scan is a snapshot. The recommended next step is a **ZAP baseline (passive)
scan in CI** on every pull request, using the `zaproxy/action-baseline` GitHub
Action against the preview stack, so header and cookie regressions such as Z-05
and Z-06 fail the build. The full active scan, which is slower and attacks
the system, stays a manual step before each release.

## 9. How to reproduce

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
cd /usr/share/zaproxy && ./zap.sh -daemon -host 127.0.0.1 -port 8090 -config api.key=$ZAP_KEY
# GUI alternative: start ZAP normally, set the browser proxy to 127.0.0.1:8090,
# browse the app, then right-click http://localhost → Attack → Active Scan.
```
