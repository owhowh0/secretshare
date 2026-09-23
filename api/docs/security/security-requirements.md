# Security requirements and compliance

This document lists the security requirements of SecretShare, traces each one to
its source in the DAS internship brief or in the project's own design, and states
whether the current code meets it. It is the entry point to the security
documentation set.

State assessed: branch `main`, commit `2b98875`, 23 September 2026.

---

## 1. Scope

In scope: the `web` (Next.js), `api` (FastAPI), `redis`, `db` (PostgreSQL),
`keycloak`, `traefik` and `tls-init` services defined in `docker-compose.yml` and
`docker-compose.preview.yml`, the realm in `keycloak/realm-export.json`, and the
GitHub Actions workflows in `.github/workflows/`.

Out of scope: the host operating systems of the staging server and of developer
machines, the Tailscale control plane, and GitHub itself. No production
deployment exists; the environments are local development, per-pull-request
previews and staging.

## 2. Sources

| Source | Reference |
|---|---|
| DAS brief | *Development of Secure Applications — PBL Project Development, Internship Guidelines*, sections "Technical Requirements" (1–5) and "Possible Security Measures" |
| Project requirements | Non-functional requirements NFR-01 to NFR-10 and security invariants 1, 3, 4, 5, 6 of the internship report, chapter 2 |
| Industry standard | OWASP Top 10:2021, mapped in `asvs-checklist.md` |

## 3. Status values

| Status | Meaning |
|---|---|
| Implemented | Enforced in code or configuration and covered by at least one automated test. |
| Partial | Enforced for part of the scope, or enforced without a test. The gap is stated. |
| Not implemented | No control exists. The requirement is planned for October–December. |

## 4. Requirements and compliance

Control identifiers refer to `api/docs/security/security-controls.md` (AUD, AUTH,
SEC, API, TLS, DB) and `docs/security/security-controls.md` (WEB). Risk identifiers
refer to `risk-register.md`.

### 4.1 Encryption and authentication (brief §1)

| ID | Requirement | Source | Status | Controls | Open risks |
|---|---|---|---|---|---|
| SR-01 | Secret content is encrypted in the sender's browser. The server receives ciphertext, an IV and wrapped keys only. | §1, §5; NFR-01; invariant 1 | Implemented | WEB-3 | R-01, R-08 |
| SR-02 | Data in transit between components is encrypted. | §1 | Partial. API → Redis and API → PostgreSQL use CA-verified TLS. The edge is HTTPS only in preview environments. Traefik → services and API → Keycloak JWKS use HTTP on the internal network. | TLS-1 | R-12, R-13 |
| SR-03 | Users authenticate through OpenID Connect, authorization code flow with PKCE. | §1, §2 | Implemented | AUTH-2 | R-15, R-16 |
| SR-04 | Multi-factor authentication is available and required. | §1 | Not implemented. The realm defines no OTP or WebAuthn required action. | — | R-03 |
| SR-05 | Passwords are stored with an adaptive hashing algorithm and a password policy is enforced. | §1 | Partial. Password storage is delegated to Keycloak, which hashes with its default algorithm. `passwordPolicy` is not set in the realm. The application stores no passwords. | — | R-03 |
| SR-06 | Repeated failed logins are throttled or locked out. | Possible measures §1 | Not implemented. `bruteForceProtected` is not set in the realm. | — | R-03 |

### 4.2 Secure APIs (brief §2)

| ID | Requirement | Source | Status | Controls | Open risks |
|---|---|---|---|---|---|
| SR-07 | All API input is validated by schema, type and size before use. | §2 | Implemented | API-1, API-2 | R-21 |
| SR-08 | API access is authorised with OAuth 2.0 bearer tokens. | §2 | Partial. `POST /keys/register` and `POST /secrets/reveal` require a token. `POST /secrets`, `POST /secrets/exists` and `GET /keys/{user_id}` do not. | AUTH-2, AUTH-3 | R-06, R-07 |
| SR-09 | Error responses disclose no internal detail and no enumeration oracle. | §2; NFR-04; invariant 5 | Implemented, with one exception: the 404 of `GET /keys/{user_id}` repeats the requested user name. | AUTH-1, SEC-4, API-2 | R-06, R-22 |

### 4.3 Frontend security (brief §3)

| ID | Requirement | Source | Status | Controls | Open risks |
|---|---|---|---|---|---|
| SR-10 | User-controlled data is escaped on output, and a Content Security Policy restricts script execution. | §3 | Implemented. React escapes output; no `dangerouslySetInnerHTML` is used. `style-src` still allows `'unsafe-inline'`. | WEB-1 | R-01, R-23 |
| SR-11 | State-changing requests cannot be forged cross-site. | §3 | Implemented by design. The API authenticates with an `Authorization` header, which a browser does not attach cross-site. Auth.js protects its own sign-in and sign-out endpoints with a CSRF token. | WEB-5 | — |
| SR-12 | Session cookies carry `HttpOnly`, `Secure` and `SameSite`. | §3 | Partial. Auth.js defaults apply: `HttpOnly` and `SameSite=Lax` always, `Secure` only when the origin is HTTPS. Not configured explicitly and not tested. | WEB-5 | R-17 |

### 4.4 Backend security (brief §4)

| ID | Requirement | Source | Status | Controls | Open risks |
|---|---|---|---|---|---|
| SR-13 | Database access uses parameterised queries or an ORM. | §4 | Implemented | DB-1 | — |
| SR-14 | Sessions time out and can be invalidated. | §4 | Partial. Keycloak access tokens expire after the realm default (5 minutes). The Auth.js session lasts 30 days and sign-out does not end the Keycloak session. | WEB-5 | R-17 |
| SR-15 | Server software and dependencies are updated to close known vulnerabilities. | §4 | Partial. Python dependencies are pinned and the web lockfile is committed. Several container images use floating tags, Keycloak runs `start-dev`, and no dependency or image scanning runs in CI. | — | R-11 |

### 4.5 Database management (brief §5)

| ID | Requirement | Source | Status | Controls | Open risks |
|---|---|---|---|---|---|
| SR-16 | Sensitive data is stored encrypted. | §5 | Partial. Secrets are stored as ciphertext only (SR-01). PostgreSQL stores public keys and audit metadata (IP address, user agent) in plaintext; volumes are not encrypted. | WEB-3, SEC-2 | R-19 |
| SR-17 | Database access follows least privilege through roles. | §5 | Not implemented. The API, Keycloak and the initialisation job share one PostgreSQL superuser. | — | R-09 |
| SR-18 | Backups are taken, protected and restorable. | §5 | Not implemented. Redis holds no persistent data by design; PostgreSQL has no backup job and no restore procedure. | — | R-18 |

### 4.6 Project-specific requirements

| ID | Requirement | Source | Status | Controls | Open risks |
|---|---|---|---|---|---|
| SR-19 | A secret is released only to its named recipient, and a denied request does not delete it. | NFR-03; IDOR (possible measures §3) | Implemented | AUTH-3, SEC-1 | R-03 |
| SR-20 | Two concurrent reveal requests never both receive a secret. | NFR-02; invariant 3 | Implemented | SEC-1 | — |
| SR-21 | Payload identifiers carry 256 bits from a CSPRNG. | NFR-06; invariant 4 | Implemented | SEC-3 | — |
| SR-22 | An unread secret expires, and the secret store does not persist to disk. | FR-04 | Implemented | SEC-2 | — |
| SR-23 | No full payload identifier, ciphertext or token is written to a log; identifiers never appear in API paths or query strings. | NFR-05; invariant 6 | Implemented for the API. The web tier receives the identifier in the query string of the share link. | AUD-2, AUD-6 | R-04 |
| SR-24 | Clients are rate-limited per real client address. | NFR-07; possible measures §2 | Implemented | API-3, API-4 | R-21 |
| SR-25 | Security-relevant events are recorded in a log the application cannot alter. | Possible measures §4; objective 4 | Partial. Create, reveal and denied reveal are recorded. The append-only trigger can be disabled by the database owner, which is the API's role. | AUD-1, AUD-3, AUD-4 | R-09 |
| SR-26 | Security incidents are detected and handled according to a documented plan. | Objective 4; expected outcome 3 | Partial. The plan exists (`incident-response-plan.md`). Keycloak event logging is disabled and no alerting exists. | — | R-10 |
| SR-27 | Personal data is limited to what is needed and is deleted after a defined period. | GDPR (report, section 3.3) | Partial. Collection is limited to IP address and user agent. No retention period or deletion job exists. | AUD-5 | R-19 |
| SR-28 | Every HTTP response carries security headers appropriate to its content type. | NFR-05; OWASP A05 | Implemented | API-5, WEB-1 | R-12 |

## 5. Summary

| Status | Count | Requirements |
|---|---|---|
| Implemented | 14 | SR-01, SR-03, SR-07, SR-09, SR-10, SR-11, SR-13, SR-19, SR-20, SR-21, SR-22, SR-23, SR-24, SR-28 |
| Partial | 10 | SR-02, SR-05, SR-08, SR-12, SR-14, SR-15, SR-16, SR-25, SR-26, SR-27 |
| Not implemented | 4 | SR-04, SR-06, SR-17, SR-18 |

## 6. Security priorities

The brief asks the team to decide which measures belong to the first MVP and which
are deferred. The decision recorded here follows the risk ratings in
`risk-register.md`.

**Implemented in September.** Measures without which the design does not hold:
browser-side encryption, OIDC authentication, recipient-bound atomic delivery,
unguessable identifiers, identifiers kept out of API request lines, validation and
size limits, rate limiting, uniform errors, internal TLS to the data stores, the
audit log and the Content Security Policy.

**Planned for October–December**, in order of risk rating:

1. Keycloak hardening: brute-force protection, password policy, MFA (OTP or
   WebAuthn), disable the password grant, restrict `webOrigins`, enforce PKCE
   (R-03, R-15).
2. Monitoring: enable Keycloak events, alert on audit write failures and on
   repeated denied reveals, add a CSP reporting endpoint (R-10).
3. Dependency and image scanning in CI, pinned image tags, Keycloak in production
   mode (R-11).
4. Least-privilege database roles for the API and Keycloak (R-09).
5. Non-extractable device keys and removal of the access token from client-side
   session data (R-02).
6. Authentication on `POST /secrets` and `GET /keys/{user_id}` (R-06, R-07).
7. Backup and restore procedure for PostgreSQL (R-18).
8. TLS and HSTS at the edge for every non-local environment (R-12).

## 7. Document set

| Document | Content |
|---|---|
| `api/docs/security/security-requirements.md` | This document |
| `api/docs/security/threat-model.md` | Assets, trust boundaries, data flows and STRIDE threats |
| `api/docs/security/risk-register.md` | Risk assessment and treatment plan |
| `api/docs/security/security-controls.md` | API controls: problem, relevance, implementation, testing, limitations |
| `docs/security/security-controls.md` | Web application controls in the same format |
| `api/docs/security/incident-response-plan.md` | Roles, severity levels, procedures and playbooks |
| `api/docs/security/asvs-checklist.md` | Mapping to OWASP Top 10:2021 |
| `api/docs/architecture/crypto-spec.md` | Algorithms, keys, envelope format and cryptographic limitations |
| `api/docs/architecture/data-model.md` | PostgreSQL schema and its security properties |
