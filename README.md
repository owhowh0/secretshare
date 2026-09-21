# SecretShare

SecretShare is a secure, ephemeral secret-sharing application featuring one-time retrieval, zero-trust end-to-end token validation via Keycloak (OAuth2 / OIDC with PKCE), FastAPI backend, Redis for ephemeral storage, PostgreSQL for persistent realms, and Traefik for unified path-based ingress routing.

---

## Table of Contents
- [Architecture & Path-Based Routing](#architecture--path-based-routing)
- [Testing Credentials](#testing-credentials)
- [Environment Variables](#environment-variables)
- [Local Development Setup](#local-development-setup)
- [Running Automated Tests](#running-automated-tests)
- [CI/CD & Ephemeral Previews](#cicd--ephemeral-previews)

---

## Architecture & Path-Based Routing

The stack avoids fragile subdomains by routing all components cleanly via path prefixes through **Traefik**:

| Component | Local URL | PR Preview URL (Ephemeral) | Description |
| :--- | :--- | :--- | :--- |
| **Web Frontend** | `http://localhost/` | `http://staging-server/pr-<N>/` | Static frontend served via `nginx:alpine` (auto-redirects from `/pr-<N>`) |
| **API & Swagger Docs** | `http://localhost/api/docs` | `http://staging-server/pr-<N>/api/docs` | FastAPI backend with OpenAPI 3.0 documentation |
| **API Healthcheck** | `http://localhost/api/health` | `http://staging-server/pr-<N>/api/health` | Service health status check |
| **Keycloak Realm** | `http://localhost/keycloak` | `http://staging-server/pr-<N>/keycloak` | Identity & Access Management (OIDC / OAuth2) |
| **Traefik Dashboard** | `http://localhost:8080/` | `http://staging-server:8080/` | Ingress and router observability |

> **Note on Nginx**: Nginx (`web`) currently acts solely as the lightweight static file server for `./web/index.html` and `./web/app.js`. Traefik is the reverse proxy and edge router. When migrating to **Next.js** later, Next.js will serve its own assets and the Nginx container will be removed without impacting backend routing.

---

## Testing Credentials

The system includes pre-provisioned testing accounts imported automatically on startup from [`keycloak/realm-export.json`](keycloak/realm-export.json):

### End-User Account (Browser & API Testing)
- **Username**: `testuser`
- **Password**: `testpassword123`
- **Email**: `test@example.com`
- **Realm**: `secretshare`
- **Client ID**: `secretshare-api`
- **Flow**: Authorization Code Flow with PKCE (SHA-256 with pure JS fallback for non-secure HTTP contexts)

### Keycloak Administrator Account
- **Username**: `admin`
- **Password**: Configured via `KEYCLOAK_ADMIN_PASSWORD` in `.env` (generated per PR preview on staging)
- **Console URL**: `http://localhost/keycloak` (local) or `http://staging-server/pr-<N>/keycloak` (preview)

### Database (PostgreSQL)
- **User**: `secretshare` (or `${POSTGRES_USER}`)
- **Password**: Configured via `POSTGRES_PASSWORD` in `.env`
- **Databases**:
  - Main App DB: `secretshare` (local) / `secretshare_pr_<PR_NUMBER>` (preview)
  - Keycloak DB: `keycloak` (local) / `keycloak_pr_<PR_NUMBER>` (preview)

---

## Environment Variables

All configuration is managed through environment variables. Copy `.env.example` to `.env` before starting.

| Variable | Required | Default | Scope | Description |
| :--- | :---: | :--- | :--- | :--- |
| `POSTGRES_USER` | No | `secretshare` | Shared | PostgreSQL username for application and Keycloak |
| `POSTGRES_PASSWORD` | **Yes** | — | Shared | Strong password for PostgreSQL authentication |
| `POSTGRES_DB` | No | `secretshare` | App | PostgreSQL database name for application data |
| `POSTGRES_PORT` | No | `5432` | DB | Local host port binding for PostgreSQL |
| `DB_HOST` | No | `db` | App / KC | Hostname of the database service container |
| `DATABASE_URL` | No | *(constructed)* | App | SQLAlchemy asyncpg connection string |
| `REDIS_HOST` | No | `redis` | App | Hostname of Redis service container |
| `REDIS_PORT` | No | `6379` | App | Port of Redis service container |
| `REDIS_URL` | No | `redis://redis:6379/0` | App | Full Redis connection URI for secret storage |
| `KEYCLOAK_ADMIN` | No | `admin` | Keycloak | Keycloak root administrator username |
| `KEYCLOAK_ADMIN_PASSWORD`| **Yes** | — | Keycloak | Password for Keycloak root administrator |
| `KEYCLOAK_DB` | No | `keycloak` | Keycloak | Dedicated database for Keycloak inside Postgres |
| `KEYCLOAK_REALM` | No | `secretshare` | Shared | Active Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | No | `secretshare-api` | Shared | Public OIDC client ID configured for SecretShare |
| `KEYCLOAK_URL` | No | `http://keycloak:8080/keycloak` | App / Web | Base URL for Keycloak OIDC issuer & JWKS |
| `KEYCLOAK_PATH` | No | `/keycloak` | Traefik | Path prefix where Keycloak is served |
| `API_ROOT_PATH` | No | `/api` | FastAPI | OpenAPI and Swagger path prefix (handles subpath routing) |
| `ENVIRONMENT` | No | `development` | FastAPI | `development` / `testing` / `production`; production fails fast if `DATABASE_URL` or `KEYCLOAK_*` are missing |
| `SECRET_TTL_SECONDS` | No | `600` | FastAPI | Default lifetime of an unread secret when the client sends no `ttl_seconds` |
| `SECRET_TTL_MIN_SECONDS` | No | `300` | FastAPI | Smallest `ttl_seconds` a client may request |
| `SECRET_TTL_MAX_SECONDS` | No | `86400` | FastAPI | Largest `ttl_seconds` a client may request |
| `MAX_PAYLOAD_BYTES` | No | `65536` | FastAPI | Max ciphertext size accepted by `POST /secrets` |
| `RATE_LIMIT_WINDOW_SECONDS` | No | `60` | FastAPI | Rate-limit window length |
| `CREATE_RATE_LIMIT` | No | `10` | FastAPI | `POST /secrets` requests per IP per window |
| `RETRIEVE_RATE_LIMIT` | No | `30` | FastAPI | `POST /secrets/reveal` requests per IP per window |
| `PR_NUMBER` | Conditional | — | Preview | Injected in preview environments for isolation (`/pr-<N>`) |
| `TEST_USER_USERNAME` | No | `testuser` | Tests | Pre-configured test username for integration tests |
| `TEST_USER_PASSWORD` | No | `testpassword123` | Tests | Pre-configured test password for integration tests |
| `TEST_USER_EMAIL` | No | `test@example.com`| Tests | Pre-configured test email address |
| `REQUIRE_KEYCLOAK` | No | `1` | Tests | When `1`, integration tests fail fast if Keycloak is down |
| `API_BASE_URL` | No | *(empty)* | Tests | Optional live API URL target (e.g. `http://localhost/api`) |
| `TRAEFIK_WEB_PORT` | No | `80` | Traefik | Host HTTP port mapping for public web ingress |
| `TRAEFIK_DASHBOARD_PORT` | No | `8080` | Traefik | Host port mapping for Traefik dashboard |

---

## Local Development Setup

### 1. Initialize Environment
```bash
cp .env.example .env
# Edit .env and supply secure passwords for POSTGRES_PASSWORD and KEYCLOAK_ADMIN_PASSWORD
```

### 2. Launch Services with Docker Compose
```bash
docker compose up -d --build
```

### 3. Verify Health
- **Web UI**: Open [http://localhost](http://localhost)
- **API Swagger**: Open [http://localhost/api/docs](http://localhost/api/docs)
- **Keycloak Console**: Open [http://localhost/keycloak](http://localhost/keycloak) (login with `admin`)
- **Login with Test Account**: Click **Login with Keycloak** and enter `testuser` / `testpassword123`

---

## Running Automated Tests

### Python Unit Tests (Fast, In-Process)
Validates API endpoints, input schemas, PyJWT token decoding, and frontend static contracts:
```bash
# In the api directory:
python -m pytest -v -m "not integration"
```

### Frontend & Path-Routing Tests
Validates DOM elements, Node.js JS syntax (`node -c`), non-secure HTTP PKCE fallback challenge computation, and subpath URL resolution:
```bash
python -m pytest -v api/tests/test_frontend_and_routing.py
```

### Live OAuth Integration Tests
Validates real token issuance with Keycloak, token exchange, protected `/api/me` claims, and authenticated one-time secret burn:
```bash
# Run against local running containers:
scripts/test_oauth.sh
```

---

## CI/CD & Ephemeral Previews

Every pull request triggers:

1. **Test API Pipeline** (`.github/workflows/test-api.yml`):
   - Runs unit tests and frontend asset tests in Python 3.12.
   - Spins up the Docker compose stack and executes live OAuth integration tests against the live API and Keycloak.
2. **PR Preview Deployment** (`.github/workflows/deploy-preview.yml`):
   - Securely deploys an isolated preview stack on the staging server via Tailscale.
   - Sets up isolated databases (`secretshare_pr_<PR_NUM>`, `keycloak_pr_<PR_NUM>`).
   - Executes a 9-step automated smoke test battery:
     1. Trailing-slash redirect verification (`/pr-<N>` &rarr; `/pr-<N>/`).
     2. Static frontend HTML & DOM elements verification.
     3. Static JS delivery (`app.js` 200 OK with PKCE logic).
     4. OpenAPI schema & Swagger verification (`/api/openapi.json`).
     5. Keycloak OIDC discovery & live token generation (`testuser`).
     6. Protected `/api/me` verification with Bearer token.
     7. Negative authentication checks (403 without token, 401 with invalid token).
     8. Authenticated secret lifecycle (creation, retrieval, and 404 burn).
     9. Anonymous secret lifecycle (creation, retrieval, and 404 burn).
   - Automatically posts the live preview URL on the pull request.