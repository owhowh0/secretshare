# Risk register

This document rates the risks that remain after the controls implemented in
September and records the treatment decided for each. Threat identifiers (T-xx)
refer to `threat-model.md`; control identifiers refer to the two
`security-controls.md` files.

State assessed: branch `main`, commit `2b98875`, 23 September 2026.

---

## 1. Method

The assessment is qualitative and follows the likelihood × impact approach of
NIST SP 800-30 Rev. 1. Each risk is rated on its **current** state, that is with
the existing controls in place, and again on its **target** state after the
planned treatment.

### 1.1 Likelihood

| Value | Level | Criterion |
|---|---|---|
| 1 | Rare | Requires privileged access to the host or network and several independent conditions. |
| 2 | Unlikely | Requires access to the internal network, the server, CI, or a victim's device. |
| 3 | Possible | Requires a valid account or specific knowledge; feasible for a motivated outsider. |
| 4 | Likely | Exploitable by any internet client with common tools. |
| 5 | Almost certain | Already observed, or exploitable without effort. |

### 1.2 Impact

| Value | Level | Criterion |
|---|---|---|
| 1 | Negligible | No effect on secrets, accounts or service. |
| 2 | Minor | Metadata disclosure, or loss of a single secret before it is read. |
| 3 | Moderate | Abuse of the service, disclosure of personal data, or loss of audit evidence. |
| 4 | Major | Takeover of one user account, or disclosure of the secrets of one user. |
| 5 | Severe | Disclosure of the secrets of many users, or control of the infrastructure. |

### 1.3 Rating

Score = likelihood × impact.

| Score | Rating | Required response |
|---|---|---|
| 1–4 | Low | Accept, or treat when convenient. |
| 5–9 | Medium | Treat within the PBL semester. |
| 10–16 | High | Treat first in the PBL semester; owner reports progress at each milestone. |
| 20–25 | Critical | Stop deployment until treated. |

No risk is rated Critical in the current state.

### 1.4 Treatment decisions

| Decision | Meaning |
|---|---|
| Mitigate | Add or change a control to reduce likelihood or impact. |
| Accept | Keep the risk; the reason is recorded. |
| Avoid | Remove the feature or configuration that causes the risk. |

Owners are team roles: Security, Backend, Frontend, DevOps.

## 2. Current risks

| ID | Risk | Threats | Existing controls | L | I | Score | Rating |
|---|---|---|---|---|---|---|---|
| R-01 | Code served to the browser by a compromised web tier, dependency or build is modified to send plaintext or keys to the attacker. | T-08, T-16 | WEB-1 | 2 | 5 | 10 | High |
| R-02 | An injected script reads the access token from the client session or exports the device private key, which is generated with `extractable: true`. | T-16 | WEB-1 | 2 | 4 | 8 | Medium |
| R-03 | A user account is taken over through password guessing or reuse: the realm has no brute-force protection, no password policy and no MFA. | T-01 | Keycloak password hashing | 3 | 4 | 12 | High |
| R-04 | The payload identifier reaches web-tier request lines and browser history through `/?id=`, `/s/<id>` and `/secret/<id>`. | T-14 | AUTH-3 limits the use of an identifier to its recipient; `replaceState` removes it from the address bar after reveal | 4 | 2 | 8 | Medium |
| R-05 | A reveal on a browser without a matching device key deletes the secret before decryption fails. | T-24 | None | 3 | 2 | 6 | Medium |
| R-06 | User names are enumerable through `GET /keys/{user_id}`, which is unauthenticated, not rate-limited, and answers 200 or 404. | T-17 | None | 4 | 2 | 8 | Medium |
| R-07 | Secrets are created without authentication: the sender is not attributable, and any registered user can receive unsolicited or misleading secrets. | T-04, T-11 | API-3 per-IP limit, SEC-2 lifetime | 3 | 3 | 9 | Medium |
| R-08 | A compromised server substitutes a recipient's public key, so later secrets are wrapped for the attacker. | T-05 | None | 1 | 5 | 5 | Medium |
| R-09 | The API, Keycloak and the initialisation job share one PostgreSQL superuser. Code execution in the API gives access to the Keycloak database and allows the audit trigger to be disabled. | T-09, T-26 | AUD-3 (bypassable), non-root API container | 2 | 5 | 10 | High |
| R-10 | Incidents are not detected: Keycloak events are disabled, audit write failures and CSP violations are not reported, and no alerting exists. | T-13 | AUD-1 (records events, no alerting) | 4 | 3 | 12 | High |
| R-11 | Known vulnerabilities remain in dependencies and images: no dependency or image scanning, floating tags (`traefik:latest`, `redis:7-alpine`, `postgres:16-alpine`), Keycloak 26.0 in `start-dev` mode. | T-29 | Pinned Python versions, committed `bun.lock` | 3 | 4 | 12 | High |
| R-12 | Traffic between browser and edge is plain HTTP outside preview environments, without HSTS. | T-19 | HTTPS through Tailscale Serve in previews | 2 | 4 | 8 | Medium |
| R-13 | Internal channels are partly unprotected: Traefik → services and API → JWKS use HTTP, TLS hostnames are not verified, Redis has no authentication. | T-07, T-10 | TLS-1, AES-GCM tag | 1 | 4 | 4 | Low |
| R-14 | The Traefik dashboard is exposed on port 8080 of all host interfaces (`--api.insecure=true`), and Traefik has the Docker socket mounted. | T-20, T-27 | Socket mounted read-only | 2 | 4 | 8 | Medium |
| R-15 | The Keycloak client allows the password grant (`directAccessGrantsEnabled`), accepts any web origin (`webOrigins: "*"`), does not require PKCE on the server side, and the realm sets `sslRequired: none`. A test user with a published password exists in the realm export. | T-01 | Implicit flow disabled | 2 | 3 | 6 | Medium |
| R-16 | The API does not verify the `iss` claim of access tokens. | T-02 | AUTH-2 verifies signature against the realm JWKS, audience and expiry | 1 | 3 | 3 | Low |
| R-17 | The Auth.js session lasts 30 days and application sign-out does not end the Keycloak session. | T-30 | Access token expiry (5 minutes) | 2 | 3 | 6 | Medium |
| R-18 | PostgreSQL data (device keys, audit log, Keycloak accounts) has no backup and no tested restore. | T-25 | None | 2 | 4 | 8 | Medium |
| R-19 | IP addresses and user agents in the audit log are kept without a retention limit. | T-15 | AUD-5 (limited collection, user agent truncated) | 3 | 2 | 6 | Medium |
| R-20 | Configuration secrets are exposed: `docker-compose.yml` falls back to a published `AUTH_SECRET`, GitHub Actions are pinned to tags rather than commit hashes, and no secret scanning runs in CI. | T-28 | `.env` excluded from git; previews limited to member pull requests | 2 | 4 | 8 | Medium |
| R-21 | Resource exhaustion: limits are per IP only, the rate limiter allows requests when Redis fails, and Redis memory has no configured ceiling. | T-22 | API-1, API-3, SEC-2 | 2 | 3 | 6 | Medium |
| R-22 | Response timing reveals the validation path, for example a JWKS cache miss for an unknown key identifier. | T-18 | AUTH-1, SEC-4 equalise content only | 1 | 2 | 2 | Low |
| R-23 | `style-src 'unsafe-inline'` allows CSS injection, which can exfiltrate attribute values or redress the page. | T-16 | WEB-1 blocks scripts; React escaping | 1 | 2 | 2 | Low |

### 2.1 Distribution

| Likelihood \ Impact | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| **5** | | | | | |
| **4** | | R-04, R-06 | R-10 | | |
| **3** | | R-05, R-19 | R-07 | R-03, R-11 | |
| **2** | | | R-15, R-17, R-21 | R-02, R-12, R-14, R-18, R-20 | R-01, R-09 |
| **1** | | R-22, R-23 | R-16 | R-13 | R-08 |

| Rating | Count |
|---|---|
| High | 5 |
| Medium | 14 |
| Low | 4 |

## 3. Treatment plan

Target dates refer to the PBL semester, October–December 2026.

| ID | Treatment | Decision | Owner | Target | Target L × I |
|---|---|---|---|---|---|
| R-01 | Add a CSP reporting endpoint; review dependency updates before merge; build only from the committed lockfile. Accept the residual risk that a fully compromised server can serve modified code. | Mitigate, accept residual | Frontend | December | 1 × 5 = 5 |
| R-02 | Generate device keys with `extractable: false`. Stop copying the access token into the client session; call the API through a server-side route that reads the token from the encrypted session cookie. | Mitigate | Frontend | October | 1 × 4 = 4 |
| R-03 | Enable `bruteForceProtected`; set a password policy (minimum length 12, not the user name, password history); require OTP or WebAuthn as a second factor. | Mitigate | Security | October | 1 × 4 = 4 |
| R-04 | Carry the identifier in the URL fragment (`/#<id>`), which the browser does not send to the server; remove the path-based redirect routes. | Mitigate | Frontend | November | 2 × 2 = 4 |
| R-05 | Send the device identifier with the reveal request; the server refuses without deleting when no `encrypted_keys` entry matches it. | Mitigate | Backend | October | 1 × 2 = 2 |
| R-06 | Require a bearer token on `GET /keys/{user_id}`, apply a rate limit, and return the same response for unknown users and users without keys. | Mitigate | Backend | October | 2 × 2 = 4 |
| R-07 | Require a bearer token on `POST /secrets`; store the sender identity in the envelope and in `audit_events.actor_user_id`; show the sender name before reveal. | Mitigate | Backend | October | 1 × 3 = 3 |
| R-08 | Display device key fingerprints; store the first key seen per recipient in the sender's browser and warn on change. | Mitigate | Security | December | 1 × 4 = 4 |
| R-09 | Create separate roles: a migration owner, an API role with `INSERT` and `SELECT` only on `audit_events`, and a Keycloak role limited to its own database. Copy audit rows to storage outside the host. | Mitigate | Backend | November | 2 × 3 = 6 |
| R-10 | Enable Keycloak login and admin events; collect container logs centrally; alert on audit write failures, on bursts of `denied` events and HTTP 429, and on CSP reports. | Mitigate | DevOps | November | 2 × 3 = 6 |
| R-11 | Enable Dependabot for pip, npm, Docker and GitHub Actions; run a dependency scanner and an image scanner in CI; pin image versions; run Keycloak with `start` on a current 26.x patch release. | Mitigate | DevOps | October | 2 × 4 = 8 |
| R-12 | Terminate TLS at the edge in every non-local environment; send HSTS; redirect HTTP to HTTPS; set the realm to `sslRequired: external`. | Mitigate | DevOps | December | 1 × 4 = 4 |
| R-13 | Issue certificates with subject alternative names and enable hostname verification; set a Redis ACL user and password; fetch the JWKS over TLS. | Mitigate | DevOps | November | 1 × 3 = 3 |
| R-14 | Remove `--api.insecure=true` or bind the dashboard to `127.0.0.1`; replace the socket mount with a read-only Docker socket proxy. | Mitigate | DevOps | October | 1 × 3 = 3 |
| R-15 | Disable the password grant outside the test realm; list explicit `webOrigins`; set `pkce.code.challenge.method` to `S256`; remove the test user from non-test deployments. | Mitigate | Security | October | 1 × 3 = 3 |
| R-16 | Pass the expected issuer to `jwt.decode` and require the `exp` and `iat` claims. | Mitigate | Backend | October | 1 × 1 = 1 |
| R-17 | Set the Auth.js session lifetime to the Keycloak SSO maximum; implement refresh-token rotation; call the Keycloak end-session endpoint on sign-out. | Mitigate | Frontend | November | 1 × 3 = 3 |
| R-18 | Schedule encrypted `pg_dump` backups of both databases to storage outside the host, keep 7 daily and 4 weekly copies, and test a restore each month. Redis is excluded by design. | Mitigate | DevOps | November | 2 × 2 = 4 |
| R-19 | Define a retention period of 90 days and a lawful basis; add a scheduled purge run by a dedicated role that the append-only trigger permits. | Mitigate | Security | November | 2 × 2 = 4 |
| R-20 | Remove the `AUTH_SECRET` fallback so the service fails to start without it; pin actions to commit hashes; add secret scanning to CI; rotate the published test credentials. | Mitigate | DevOps | October | 1 × 4 = 4 |
| R-21 | Set Redis `maxmemory` with `noeviction`, so that a full store rejects writes (HTTP 503) instead of evicting secrets; add per-user limits once creation requires authentication. | Mitigate | Backend | November | 2 × 2 = 4 |
| R-22 | Measure response timing against a live Keycloak; treat only if a measurable difference is found. | Accept | Backend | December | 1 × 2 = 2 |
| R-23 | Move inline styles into `globals.css` and remove `'unsafe-inline'` from `style-src`. | Mitigate | Frontend | November | 1 × 1 = 1 |

## 4. Review

The register is reviewed at each PBL milestone and after any incident handled
under `incident-response-plan.md`. A risk is closed when its treatment is merged,
a test demonstrates the control, and the corresponding entry in
`security-controls.md` is added or updated.
