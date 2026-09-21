# SecretShare

SecretShare is a secure, ephemeral secret-sharing platform featuring **client-side end-to-end hybrid encryption** (Web Crypto API: ECDH P-256 + AES-GCM-256), zero-trust authentication via **Keycloak** (OAuth2 / OIDC with PKCE), **Next.js** frontend with NextAuth, **FastAPI** backend, ephemeral storage with **Redis**, audit logging in **PostgreSQL**, internal **TLS encryption** across datastores, and unified edge routing with **Traefik**.

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
- **Client-Side Hybrid Encryption**: Recipients publish ECDH P-256 device public keys. Senders encrypt a random AES-GCM-256 key with the recipient's public key; only the recipient's private key can decrypt the secret.
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
| **Traefik Dashboard** | `http://localhost:8080/` | *Internal only* | Ingress and router observability |

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

The default `docker-compose.yml` is configured as a turnkey, self-contained example stack. Anyone can clone the repository and launch the full application immediately without manual setup:

```bash
# 1. Clone the repository
git clone https://github.com/owhowh0/secretshare.git
cd secretshare

# 2. Deploy the full stack
docker compose up -d --build
```

That's it! Docker Compose will automatically:
- Create required networks and volumes.
- Generate local TLS certificates for datastores via `tls-init`.
- Bootstrap the PostgreSQL database and Keycloak schema.
- Import the Keycloak realm and test accounts.
- Build and start the Next.js frontend and FastAPI backend.

### Optional Customization
To customize passwords, ports, or secrets, copy `.env.example` to `.env` before running Compose:
```bash
cp .env.example .env
# Edit .env with your desired settings
docker compose up -d --build
```

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
- **Password**: `admin` (or configured via `KEYCLOAK_ADMIN_PASSWORD` in `.env`)
- **Console URL**: `http://localhost/keycloak`

### Database (PostgreSQL)
- **User**: `secretshare`
- **Password**: `secretshare` (or configured via `POSTGRES_PASSWORD` in `.env`)
- **Databases**:
  - Main App DB: `secretshare`
  - Keycloak DB: `keycloak`

---

## Environment Variables

| Variable | Default | Scope | Description |
| :--- | :--- | :--- | :--- |
| `POSTGRES_USER` | `secretshare` | DB / App | PostgreSQL username |
| `POSTGRES_PASSWORD` | `secretshare` | DB / App | PostgreSQL password |
| `POSTGRES_DB` | `secretshare` | App | Application database name |
| `POSTGRES_PORT` | `5432` | DB | Host port binding for PostgreSQL |
| `DB_HOST` | `db` | App / KC | Hostname of the PostgreSQL service |
| `REDIS_HOST` | `redis` | App | Hostname of the Redis service |
| `REDIS_PORT` | `6379` | App | Port of the Redis service |
| `REDIS_URL` | `rediss://redis:6379/0` | App | Redis connection URI with TLS (`rediss://`) |
| `TLS_CA_CERT` | `/certs/ca.crt` | App | Path to trusted CA certificate for internal TLS |
| `KEYCLOAK_ADMIN` | `admin` | Keycloak | Keycloak administrator username |
| `KEYCLOAK_ADMIN_PASSWORD`| `admin` | Keycloak | Keycloak administrator password |
| `KEYCLOAK_DB` | `keycloak` | Keycloak | Dedicated Keycloak database name |
| `KEYCLOAK_REALM` | `secretshare` | Shared | Active Keycloak realm |
| `KEYCLOAK_CLIENT_ID` | `secretshare-api` | Shared | Public OIDC client ID |
| `KEYCLOAK_URL` | `http://keycloak:8080/keycloak` | App / Web | Keycloak OIDC issuer URL |
| `KEYCLOAK_PATH` | `/keycloak` | Traefik | Ingress path prefix for Keycloak |
| `AUTH_SECRET` | `default_dev_auth_secret_must_be_32_characters` | NextAuth | 32-character secret for NextAuth session encryption |
| `API_ROOT_PATH` | `/api` | FastAPI | Ingress path prefix for FastAPI |
| `SECRET_TTL_SECONDS` | `600` | FastAPI | Default unread secret TTL (10 minutes) |
| `SECRET_TTL_MIN_SECONDS` | `300` | FastAPI | Minimum secret TTL (5 minutes) |
| `SECRET_TTL_MAX_SECONDS` | `86400` | FastAPI | Maximum secret TTL (24 hours) |
| `MAX_PAYLOAD_BYTES` | `65536` | FastAPI | Maximum ciphertext size (64 KB) |
| `TRAEFIK_WEB_PORT` | `80` | Traefik | Host HTTP ingress port |
| `TRAEFIK_DASHBOARD_PORT`| `8080` | Traefik | Host port for Traefik dashboard |

---

## End-to-End Hybrid Encryption

SecretShare implements zero-knowledge encryption directly inside the browser using standard Web Crypto primitives:

1. **Device Key Registration**:
   - Each authenticated user generates an **ECDH P-256** key pair in their browser.
   - The private key is stored securely in IndexedDB; the public key is registered with the backend at `POST /keys/device`.
2. **Secret Creation (Sender)**:
   - Sender fetches the recipient's ECDH public key from `GET /keys/device/{user_id}`.
   - Sender generates a random **AES-256-GCM** content encryption key (CEK).
   - The secret payload is encrypted with the CEK.
   - Sender derives a shared secret via ECDH and encrypts the CEK.
   - The encrypted payload is posted to `POST /secrets`.
3. **Secret Retrieval (Recipient)**:
   - Recipient fetches the encrypted payload using `POST /secrets/reveal`.
   - The payload is burned immediately from Redis (one-time read).
   - Recipient decrypts the CEK using their private ECDH key and decrypts the secret in the browser.

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
   - Runs on pull requests and pushes to development branches.
   - Executes unit tests, migration checks, and full OAuth integration tests against Dockerized dependencies.
2. **TLS Verification** ([`test-tls.yml`](.github/workflows/test-tls.yml)):
   - Verifies certificate generation script, permissions, and TLS settings.
3. **Ephemeral PR Previews** ([`deploy-preview.yml`](.github/workflows/deploy-preview.yml)):
   - Automatically provisions an isolated preview stack per pull request on the staging server via Tailscale.
   - Provides full HTTPS on a dedicated subdomain (`https://pr-<N>.<domain>/`).
   - Runs automated end-to-end smoke tests (auth, secret lifecycle, routing).
4. **Staging Deployment** ([`deploy-staging.yml`](.github/workflows/deploy-staging.yml)):
   - **Manually executable via `workflow_dispatch` (only on `main`)**: Deploys the latest `main` branch to the permanent staging environment via Tailscale SSH on demand.
