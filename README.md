# SecretShare

SecretShare is a secure, ephemeral secret-sharing platform featuring **client-side end-to-end hybrid encryption** (Web Crypto API: RSA-OAEP 2048 + AES-GCM-256), zero-trust authentication via **Keycloak** (OAuth2 / OIDC with PKCE), **Next.js** frontend with NextAuth, **FastAPI** backend, ephemeral storage with **Redis**, audit logging in **PostgreSQL**, internal **TLS encryption** across datastores, and unified edge routing with **Traefik**.

---

## Table of Contents
- [Key Features](#key-features)
- [Architecture & Ingress Routing](#architecture--ingress-routing)
- [Quick Start (One-Command Deployment)](#quick-start-one-command-deployment)
- [Testing Credentials](#testing-credentials)
- [Environment Variables](#environment-variables)
- [End-to-End Hybrid Encryption](#end-to-end-hybrid-encryption)
- [Running Automated Tests](#running-automated-tests)
- [CI/CD & Deployment Workflows](#cicd--deployment-workflows)

---

## Key Features

- **Zero-Knowledge Architecture**: Secrets are encrypted in the browser before transmission using the Web Crypto API. The server only stores opaque ciphertext.
- **One-Time Burn & Ephemeral TTL**: Secrets are automatically deleted upon first retrieval (burn-on-read) or when their configurable TTL expires.
- **Client-Side Hybrid Encryption**: Recipients publish device public keys. Senders encrypt a random AES-GCM-256 key with the recipient's public key; only the recipient's private key can decrypt the secret.
- **Shareable Links & Burn Warning**: Creating a secret produces a direct shareable link (`/?id=<payload_id>`). Opening the link automatically verifies existence and prompts a burn-after-reading warning notice before one-time retrieval.
- **Internal Datastore TLS**: Both PostgreSQL and Redis communicate over TLS using certificates provisioned at boot by an automated `tls-init` service.
- **OIDC / OAuth2 with PKCE**: Integrated Keycloak realm pre-provisioned for browser and API authentication.
- **Edge Path-Based Routing**: Traefik handles all ingress routing on a single port without complex host subdomain configurations.

---

## Architecture & Ingress Routing

All incoming traffic enters via **Traefik**, which routes requests cleanly by path prefix:

| Component | Local URL | PR Preview URL (Ephemeral) | Description |
| :--- | :--- | :--- | :--- |
| **Web Frontend** | `http://localhost/` | `https://pr-<N>.<domain>/` | Next.js (React) application with NextAuth |
| **API & Swagger Docs** | `http://localhost/api/docs` | `https://pr-<N>.<domain>/api/docs` | FastAPI backend with OpenAPI 3.0 documentation |
| **API Healthcheck** | `http://localhost/api/health` | `https://pr-<N>.<domain>/api/health` | Service health status check |
| **Keycloak Realm** | `http://localhost/keycloak` | `https://pr-<N>.<domain>/keycloak` | Identity & Access Management (OIDC / OAuth2) |
| **Traefik Dashboard** | `http://127.0.0.1:8080/` | *Disabled* | Ingress and router observability (localhost only) |

### Internal Datastore Topology
```
                     ┌──────────────────────────────────────────────┐
                     │          Docker Network: traefik-net         │
                     │                                              │
  Public Traffic ──► │  Traefik (:80) ──┬──► Next.js Web (:3000)    │
                     │                  ├──► Keycloak (:8080)       │
                     │                  └──► FastAPI (:8000)        │
                     └──────────────────────────────┬───────────────┘
                                                    │
                     ┌──────────────────────────────▼───────────────┐
                     │          Docker Network: default             │
                     │                                              │
                     │  FastAPI (:8000)                             │
                     │    ├── (TLS via CA) ──► PostgreSQL (:5432)   │
                     │    └── (TLS via CA) ──► Redis (:6379)        │
                     │                                              │
                     │  tls-init: Provisions self-signed CA & certs │
                     └──────────────────────────────────────────────┘
```

---

## Quick Start (One-Command Deployment)

The `docker-compose.preview.yml` compose file is a self-contained example stack. The compose files ship **no fallback secrets**, so the first step generates a `.env` with random ones:

```bash
# 1. Clone the repository
git clone https://github.com/owhowh0/secretshare.git
cd secretshare

# 2. Create .env with random passwords and AUTH_SECRET (once; never overwrites)
sh scripts/init-env.sh

# 3. Ensure shared network exists
docker network create traefik-net 2>/dev/null || true

# 4. Deploy the example preview stack
docker compose -f docker-compose.preview.yml up -d --build
```

Compose will automatically:
- Create required networks and volumes.
- Generate local TLS certificates for datastores via `tls-init`.
- Bootstrap the PostgreSQL database and Keycloak schema.
- Import the Keycloak realm and test accounts.
- Build and start the Next.js frontend and FastAPI backend.

### Production / Staging vs. Development

`docker-compose.yml` is the **staging/production** stack: the API runs with `ENVIRONMENT=production` (it refuses to start if `DATABASE_URL` or a `KEYCLOAK_*` setting is missing) and Keycloak runs in production mode (`start`). `docker-compose.dev.yml` is a small override that switches both back to development (`ENVIRONMENT=development`, Keycloak `start-dev`).

```bash
sh scripts/init-env.sh                                # once; or copy .env.example and fill every placeholder
docker network create traefik-net 2>/dev/null || true # required: the stack joins this external network

# Staging / production
docker compose up -d --build

# Local development
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Compose stops with an error such as `AUTH_SECRET must be set in .env` if a required secret is missing; there are no built-in default passwords.

---

## Testing Credentials

The system includes pre-provisioned testing accounts imported automatically on startup from [`keycloak/realm-export.json`](keycloak/realm-export.json):

### End-User Account (Browser & API Testing)
- **Username**: `testuser`
- **Password**: `testpassword123`
- **Email**: `test@example.com`
- **Realm**: `secretshare`
- **Client ID**: `secretshare-api`
- **Flow**: Authorization Code Flow with PKCE

### Keycloak Administrator Account
- **Username**: `admin`
- **Password**: the value of `KEYCLOAK_ADMIN_PASSWORD` in your `.env` (no default)
- **Console URL**: `http://localhost/keycloak`

### Database (PostgreSQL)
- **User**: `secretshare`
- **Password**: the value of `POSTGRES_PASSWORD` in your `.env` (no default)
- **Databases**:
  - Main App DB: `secretshare`
  - Keycloak DB: `keycloak`

---

## Environment Variables

| Variable | Default | Scope | Description |
| :--- | :--- | :--- | :--- |
| `POSTGRES_USER` | `secretshare` | DB / App | PostgreSQL username |
| `POSTGRES_PASSWORD` | **required** | DB / App | PostgreSQL password |
| `POSTGRES_DB` | `secretshare` | App | Application database name |
| `POSTGRES_PORT` | `5432` | DB | Host port binding for PostgreSQL |
| `DB_HOST` | `db` | App / KC | Hostname of the PostgreSQL service |
| `REDIS_HOST` | `redis` | App | Hostname of the Redis service |
| `REDIS_PORT` | `6379` | App | Port of the Redis service |
| `REDIS_URL` | `rediss://redis:6379/0` | App | Redis connection URI. Compose Redis is TLS-only, so it must be `rediss://`; leave unset to use the default |
| `TLS_CA_CERT` | `/certs/ca.crt` | App | Path to trusted CA certificate for internal TLS |
| `KEYCLOAK_ADMIN` | `admin` | Keycloak | Keycloak administrator username |
| `KEYCLOAK_ADMIN_PASSWORD`| **required** | Keycloak | Keycloak administrator password |
| `KEYCLOAK_DB` | `keycloak` | Keycloak | Dedicated Keycloak database name |
| `KEYCLOAK_REALM` | `secretshare` | Shared | Active Keycloak realm |
| `KEYCLOAK_CLIENT_ID` | `secretshare-api` | Shared | Public OIDC client ID |
| `KEYCLOAK_URL` | `http://keycloak:8080/keycloak` | App / Web | Keycloak OIDC issuer URL |
| `KEYCLOAK_PATH` | `/keycloak` | Traefik | Ingress path prefix for Keycloak |
| `AUTH_SECRET` | **required** | NextAuth | Secret (≥ 32 characters) for NextAuth session encryption, e.g. `openssl rand -hex 32` |
| `ENVIRONMENT` | set by compose file | FastAPI | `production` in `docker-compose.yml`, `development` with `docker-compose.dev.yml`; production fails fast on missing settings |
| `API_ROOT_PATH` | `/api` | FastAPI | Ingress path prefix for FastAPI |
| `REDIS_CONNECT_TIMEOUT_SECONDS` / `REDIS_SOCKET_TIMEOUT_SECONDS` | `3` / `5` | FastAPI | Redis connect / per-command timeout; a hung Redis yields `503` instead of a hanging request |
| `DB_CONNECT_TIMEOUT_SECONDS` / `DB_COMMAND_TIMEOUT_SECONDS` / `DB_POOL_TIMEOUT_SECONDS` | `5` / `10` / `10` | FastAPI | PostgreSQL connect / per-query / wait-for-pooled-connection timeouts |
| `JWKS_TIMEOUT_SECONDS` | `5` | FastAPI | Timeout for fetching Keycloak's signing keys (`503` on expiry) |
| `SECRET_TTL_SECONDS` | `600` | FastAPI | Default unread secret TTL (10 minutes) |
| `SECRET_TTL_MIN_SECONDS` | `300` | FastAPI | Minimum secret TTL (5 minutes) |
| `SECRET_TTL_MAX_SECONDS` | `86400` | FastAPI | Maximum secret TTL (24 hours) |
| `MAX_PAYLOAD_BYTES` | `65536` | FastAPI | Maximum ciphertext size (64 KB) |
| `TRUSTED_PROXIES` | `127.0.0.1/32,::1/128` (compose: private ranges) | FastAPI | Proxies whose `X-Forwarded-For` is trusted to identify the client for rate limits and audit |
| `TRAEFIK_WEB_PORT` | `80` | Traefik | Host HTTP ingress port |
| `TRAEFIK_DASHBOARD_PORT`| `8080` | Traefik | Host port for Traefik dashboard |

---

## End-to-End Hybrid Encryption

SecretShare implements zero-knowledge encryption directly inside the browser using standard Web Crypto primitives:

1. **Device Key Registration**:
   - Each authenticated user generates an RSA-OAEP key pair in their browser.
   - The key pair is stored in IndexedDB (the private key is currently generated as extractable, see R-02 in `api/docs/security/risk-register.md`); the public key is registered with the backend at `POST /api/keys/register`.
2. **Secret Creation (Sender)**:
   - Sender fetches the recipient's active device public keys from `GET /api/keys/{user_id}`.
   - Sender generates a random **AES-256-GCM** content encryption key (CEK).
   - The secret payload is encrypted with the CEK.
   - Sender encrypts the CEK for each recipient device using RSA-OAEP.
   - The encrypted payload is posted to `POST /api/secrets`.
   - The sender receives the `payload_id` and a direct shareable link (`https://<domain>/?id=<payload_id>`) with a copy button.
3. **Secret Retrieval (Recipient)**:
   - Recipient accesses the shareable link (or pastes the payload ID into the manual retrieval field).
   - A non-destructive existence check runs (`POST /api/secrets/exists`), and if valid, displays the **Burn-After-Reading Warning** notice modal.
   - If not authenticated, the recipient is prompted to log in via Keycloak.
   - Upon clicking "Reveal & Burn", the recipient calls `POST /api/secrets/reveal` with their Bearer token.
   - The payload is burned atomically from Redis (one-time read).
   - Recipient decrypts the CEK using their device private key and decrypts the secret plaintext in the browser.

---

## Running Automated Tests

### Python Unit Tests
```bash
cd api
pytest tests/ -v -m "not integration"
```

### TLS Certificate & Configuration Tests
```bash
cd api
pytest tests/test_tls.py -v
```

### Live OAuth Integration Tests
```bash
# Requires running Docker stack
cd api
python -m pytest -v -m integration tests/test_oauth_integration.py
```

---

## CI/CD & Deployment Workflows

GitHub Actions workflows are defined in [`.github/workflows/`](.github/workflows/):

1. **API & Security Tests** ([`test-api.yml`](.github/workflows/test-api.yml)):
   - Runs on pull requests and pushes to development branches (`main`, `develop`, `feat/**`).
   - Executes `ruff check` linting, database migrations, unit & security tests, and live OAuth integration tests.
   - Publishes JUnit XML test reports, Cobertura coverage XML artifacts, and step summaries to `$GITHUB_STEP_SUMMARY`.
2. **TLS Verification** ([`test-tls.yml`](.github/workflows/test-tls.yml)):
   - Verifies certificate generation script, permissions, SSL contexts, and TLS settings.
   - Generates coverage reports and JUnit artifacts.
3. **Security & Dependency Audit** ([`security.yml`](.github/workflows/security.yml)):
   - Runs Gitleaks secret scanner on full Git history to prevent credential leaks.
   - Performs Python SCA via `pip-audit` on `api/requirements.txt`.
   - Performs frontend dependency auditing via `bun audit` on `web/bun.lock`.
4. **Ephemeral PR Previews** ([`deploy-preview.yml`](.github/workflows/deploy-preview.yml)):
   - Automatically provisions an isolated preview stack per pull request on the staging server via Tailscale.
   - Provides full HTTPS on a dedicated subdomain (`https://pr-<N>.<domain>/`).
   - Runs automated end-to-end smoke tests (auth, secret lifecycle, routing).
5. **Staging Deployment** ([`deploy-staging.yml`](.github/workflows/deploy-staging.yml)):
   - **Manually executable via `workflow_dispatch` (only on `main`)**: Deploys the latest `main` branch to the permanent staging environment via Tailscale SSH on demand.
   - Automatically initializes `.env` if missing via `scripts/init-env.sh`, protects against port collisions with preview Traefik, and verifies post-deployment health via `wait_services_ready.sh` and `test_web_routing.sh`.

### Branch Protection & Merge Enforcement (`main`)

To ensure stability and prevent broken builds or regression on `main`:
- **No Direct Pushes**: Direct pushes to `main` are rejected. All changes must be proposed via pull requests.
- **Required Status Checks**: Merging requires passing status checks:
  - `Run API tests` (`test-api.yml`)
  - `Run OAuth live integration tests` (`test-api.yml`)
  - `Run TLS tests` (`test-tls.yml`)
  - `Secret scanning (Gitleaks)` (`security.yml`)
  - `Python dependency audit (pip-audit)` (`security.yml`)
  - `Frontend dependency audit (bun audit)` (`security.yml`)
- **Strict Linear History**: Branches must be up to date with `main` before merging.
- **Audit Evidence**: Detailed policy settings and rejection evidence are documented in [branch-protection-rules.md](docs/security/evidence/branch-protection-rules.md).
