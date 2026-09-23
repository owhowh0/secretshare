# Compliance checklist — OWASP Top 10:2021

This checklist maps SecretShare to the ten categories of the OWASP Top 10:2021, the
standard cited in the internship report. The file keeps the name given in the
initial project structure; a verification against the OWASP Application Security
Verification Standard (ASVS) is not part of this document.

State assessed: branch `main`, commit `2b98875`, 23 September 2026.

Control identifiers refer to `api/docs/security/security-controls.md` and
`docs/security/security-controls.md`; risk identifiers refer to `risk-register.md`.

| Status | Meaning |
|---|---|
| Addressed | A control exists and is tested, or the weakness cannot occur in the design. |
| Partial | A control exists with a documented gap. |
| Open | No control exists; a risk is recorded. |

---

## A01 Broken Access Control

| Check | Status | Evidence | Risk |
|---|---|---|---|
| A secret is released only to its recipient (object-level authorisation). | Addressed | AUTH-3, SEC-1 | — |
| A denied request does not change the object. | Addressed | SEC-1 | — |
| A device key is registered only for the identity in the caller's token. | Addressed | AUTH-2; `tests/test_keys.py` | — |
| Every endpoint that exposes or creates data requires authentication. | Open | `POST /secrets`, `POST /secrets/exists` and `GET /keys/{user_id}` accept anonymous calls. | R-06, R-07 |
| Cross-origin requests are restricted. | Addressed | API-5 (CORS allowlist); all components share one origin behind Traefik. | — |
| Administrative interfaces are not publicly reachable. | Open | Traefik dashboard on port 8080 with `--api.insecure=true`; Keycloak admin console under `/keycloak/admin` through the public edge. | R-14 |

## A02 Cryptographic Failures

| Check | Status | Evidence | Risk |
|---|---|---|---|
| Sensitive content is encrypted before it leaves the client. | Addressed | WEB-3; `api/docs/architecture/crypto-spec.md` | R-01 |
| Current algorithms with adequate parameters are used. | Addressed | AES-256-GCM, RSA-OAEP-2048 with SHA-256, RS256. RSA-2048 is below the 3072 bits of the initial design. | — |
| Randomness comes from a CSPRNG. | Addressed | SEC-3 (`secrets.token_urlsafe`); `crypto.getRandomValues` in WEB-3 | — |
| Private keys cannot be exported. | Open | Device keys are generated with `extractable: true`. | R-02 |
| Data in transit is encrypted on every hop. | Partial | TLS-1 covers API → Redis and API → PostgreSQL; the edge is HTTPS in previews only; internal HTTP hops remain. | R-12, R-13 |
| Passwords are stored with an adaptive hash. | Addressed | Delegated to Keycloak. | — |
| Responses with sensitive data are not cached. | Addressed | API-5 (`Cache-Control: no-store`) | — |
| Personal data at rest is minimised. | Partial | AUD-5; no retention period. | R-19 |

## A03 Injection

| Check | Status | Evidence | Risk |
|---|---|---|---|
| SQL is built with bound parameters only. | Addressed | DB-1. No test submits injection payloads. | — |
| Redis scripts receive input as arguments, not as code. | Addressed | DB-1, SEC-1 (`KEYS` / `ARGV`) | — |
| Output is encoded for its context. | Addressed | React escaping; no `dangerouslySetInnerHTML` in `web/app` | — |
| Injected scripts are blocked by CSP. | Addressed | WEB-1, tested in a headless browser | R-01 |
| Injected styles are blocked by CSP. | Partial | `style-src 'unsafe-inline'` | R-23 |
| All input is validated by schema and size. | Addressed | API-1, API-2 | — |

## A04 Insecure Design

| Check | Status | Evidence | Risk |
|---|---|---|---|
| Threats and security requirements are documented. | Addressed | `threat-model.md`, `security-requirements.md` | — |
| Security properties are stated as testable invariants. | Addressed | Invariants 1, 3, 4, 5, 6; `tests/security/` | — |
| Automated clients cannot consume a secret. | Addressed | WEB-4 | — |
| A reveal cannot destroy a secret that the device cannot decrypt. | Open | Burn precedes decryption. | R-05 |
| The recipient can identify the sender. | Open | Anonymous, unsigned envelopes. | R-07 |
| Resource consumption per client is bounded. | Partial | API-1, API-3, SEC-2; limiter fails open; no Redis memory ceiling. | R-21 |

## A05 Security Misconfiguration

| Check | Status | Evidence | Risk |
|---|---|---|---|
| Security headers are set on every response. | Addressed | API-5, WEB-1 | — |
| Errors return no stack traces or internal detail. | Addressed | API-2, AUTH-1, SEC-4 | — |
| Services run in production mode with hardened settings. | Open | Keycloak `start-dev`; realm `sslRequired: none`; password grant enabled; `webOrigins: "*"`. | R-11, R-15 |
| No default or published credentials are accepted. | Open | `AUTH_SECRET` fallback in `docker-compose.yml`; test user in the realm export. | R-15, R-20 |
| Documentation endpoints are restricted. | Partial | Swagger UI is public in every environment with a relaxed CSP. | — |
| Data stores are not exposed and do not persist secrets. | Addressed | Redis and PostgreSQL ports bound to `127.0.0.1`; Redis `--save "" --appendonly no` (SEC-2). | — |
| Containers run without root privileges. | Addressed | `api` runs as `appuser` (UID 10001), `web` as `nextjs` (UID 1001). | — |

## A06 Vulnerable and Outdated Components

| Check | Status | Evidence | Risk |
|---|---|---|---|
| Dependency versions are fixed. | Partial | `api/requirements.txt` pins exact versions without hashes; `web/bun.lock` is installed with `--frozen-lockfile`; `package.json` uses ranges. | R-11 |
| Container images are fixed. | Open | `traefik:latest`, `redis:7-alpine`, `postgres:16-alpine`, `alpine:3`. | R-11 |
| Known vulnerabilities are detected automatically. | Open | No dependency, image or code scanning in CI. | R-11 |
| Components are on supported, patched releases. | Open | Keycloak pinned to 26.0. | R-11 |

## A07 Identification and Authentication Failures

| Check | Status | Evidence | Risk |
|---|---|---|---|
| Authentication uses a standard protocol. | Addressed | OIDC authorization code flow with PKCE through Keycloak and Auth.js | — |
| Multi-factor authentication is available. | Open | No OTP or WebAuthn required action in the realm. | R-03 |
| Repeated failed logins are throttled. | Open | `bruteForceProtected` not set. | R-03 |
| A password policy is enforced. | Open | `passwordPolicy` not set. | R-03 |
| Tokens are fully validated. | Partial | AUTH-2 verifies signature, algorithm, audience and expiry; not the issuer. | R-16 |
| Authentication failures are indistinguishable. | Addressed | AUTH-1 | — |
| User names cannot be enumerated. | Open | `GET /keys/{user_id}` answers 200 or 404. | R-06 |
| Sessions expire and logout ends them. | Partial | WEB-5: 30-day session, no Keycloak end-session call. | R-17 |

## A08 Software and Data Integrity Failures

| Check | Status | Evidence | Risk |
|---|---|---|---|
| Every pull request runs the automated tests, and a skipped security test fails the run. | Addressed | `test-api.yml`, `test-tls.yml`, preview smoke tests. Whether branch protection requires these checks before merge is a repository setting not recorded here. | — |
| CI actions are pinned to immutable versions. | Partial | Pinned to major tags (`@v4`, `@v5`, `@v2`), not commit hashes. | R-20 |
| Deployment credentials are exposed only to trusted workflows. | Addressed | Preview deployment runs only for pull requests from the repository by members. | — |
| Users can verify the integrity of the client code. | Open | Code is served by the relay without signing or pinning. | R-01 |
| Untrusted data is not deserialised into objects. | Addressed | JSON only; the burn script decodes with `pcall(cjson.decode, …)`. | — |

## A09 Security Logging and Monitoring Failures

| Check | Status | Evidence | Risk |
|---|---|---|---|
| Security events are recorded. | Partial | AUD-1 records create, reveal and denied reveal. Token rejections go to the application log only. Key registration and logins are not recorded. | R-10 |
| Logs contain no secrets. | Addressed | AUD-2, AUD-6, AUTH-1 | R-04 |
| Audit records resist tampering. | Partial | AUD-3; bypassable by the owner role. | R-09 |
| Events are monitored and raise alerts. | Open | No alerting; Keycloak events disabled. | R-10 |
| An incident response plan exists. | Addressed | `incident-response-plan.md` | — |
| Log retention is defined. | Open | No retention period. | R-19 |

## A10 Server-Side Request Forgery

| Check | Status | Evidence | Risk |
|---|---|---|---|
| The server makes no request to a destination supplied by the client. | Addressed | The API fetches only the JWKS at the configured `KEYCLOAK_URL`; the web server calls only the configured issuer and the fixed `INTERNAL_API_URL`. | — |

---

## Summary

| Category | Addressed | Partial | Open |
|---|---|---|---|
| A01 Broken Access Control | 4 | 0 | 2 |
| A02 Cryptographic Failures | 5 | 2 | 1 |
| A03 Injection | 5 | 1 | 0 |
| A04 Insecure Design | 3 | 1 | 2 |
| A05 Security Misconfiguration | 4 | 1 | 2 |
| A06 Vulnerable and Outdated Components | 0 | 1 | 3 |
| A07 Identification and Authentication Failures | 2 | 2 | 4 |
| A08 Software and Data Integrity Failures | 3 | 1 | 1 |
| A09 Security Logging and Monitoring Failures | 2 | 2 | 2 |
| A10 Server-Side Request Forgery | 1 | 0 | 0 |
| **Total** | **29** | **11** | **17** |
