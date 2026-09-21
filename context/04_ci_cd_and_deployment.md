# CI/CD & Preview Deployment Pipeline

SecretShare uses GitHub Actions for automated unit/integration testing and ephemeral preview deployments over Tailscale.

---

## 1. Test API Workflow (`.github/workflows/test-api.yml`)

Runs on pull requests and pushes to `main`, `develop`, and `feat/**`.

### Pipeline Jobs:
1. **`test` (Unit, Security, and Contract Tests)**:
   - Sets up Python 3.12 and installs dependencies via `uv`.
   - Executes full test suite excluding live integration tests:
     ```bash
     uv run pytest -c api/pytest.ini api/tests/ -m "not integration"
     ```
   - Covers:
     - Centralized Pydantic configuration (`test_config.py`).
     - Alembic database migration execution (`test_migrate.py`).
     - Secret TTL bounds, byte limits, and domain exceptions (`test_secrets.py`).
     - Security invariants: access log redaction, audit logging without plaintext leakage, and non-disclosure of user input on 422 errors (`api/tests/security/`).
     - Subdomain and reverse proxy routing contracts (`test_frontend_and_routing.py`).
2. **`oauth-integration` (Live Docker Integration Tests)**:
   - Spins up the local container stack (`db`, `redis`, `keycloak`, `traefik`, `web`, `api`).
   - Verifies container health endpoints.
   - Executes live OAuth Authorization Code / direct grant integration tests (`api/tests/test_oauth_integration.py`).

---

## 2. Preview Deployment Workflow (`.github/workflows/deploy-preview.yml`)

Automatically deploys an isolated, ephemeral preview environment for every Pull Request from contributors.

### Prerequisites & Infrastructure:
- **Tailscale Authentication**: GitHub runner authenticates to Tailscale using `tailscale/github-action@v2` with `TS_OAUTH_CLIENT_ID` and `TS_OAUTH_SECRET`.
- **Target Host**: Direct SSH connection to `staging-server` as `root` over the tailnet.
- **Isolated Worktrees**: Managed in `/opt/secretshare/worktrees/pr-${PR_NUM}`.

### Deployment Process:
1. **Host Setup**:
   - Ensures shared external Docker network `traefik-net` and global `traefik` router are running.
   - Clones or updates repository worktree to the PR's `FETCH_HEAD`.
2. **Environment & Secrets Generation**:
   - Generates random cryptographic passwords for PostgreSQL, Keycloak Admin, and NextAuth `AUTH_SECRET`.
   - Injects `PR_HOSTNAME="pr-${PR_NUM}.${TAILNET_NAME}"` and `TS_AUTHKEY`.
3. **Tailscale Ingress Configuration**:
   - Customizes `tailscale/serve.json` with the PR hostname.
   - Mounts `/dev/net/tun` with `NET_ADMIN` and `NET_RAW` capabilities.
4. **Stack Launch & Self-Healing**:
   - Launches `docker-compose.preview.yml`.
   - If initial start fails, automatically prunes stale project volumes and retries cleanly.
5. **Keycloak Database Sync**:
   - Injects `https://${PR_HOSTNAME}/*` into Keycloak's `redirect_uris` and `post_auth_redirect_uris` tables in PostgreSQL to handle persistent database volumes.
6. **Tailscale Serve Activation**:
   - Waits for the Tailscale container state to reach `Running`.
   - Obtains ephemeral IP address via `tailscale ip -4` and temporarily maps it in `/etc/hosts` for runner-local resolution.
   - Activates dual HTTPS/HTTP proxying:
     ```bash
     tailscale serve --bg --https=443 / http://traefik:80
     tailscale serve --bg --http=80 http://traefik:80
     ```

---

## 3. Automated Preview Verification Battery

Before marking the deployment successful, the runner executes automated verification scripts against the live HTTPS preview URL (`${PREVIEW_URL}`):

1. **`wait_services_ready.sh`**:
   Polls Next.js web (`/`), FastAPI (`/api/health`), and Keycloak (`/keycloak/realms/secretshare`) until all services return HTTP 200.
2. **`test_web_routing.sh`**:
   Validates that the Next.js frontend is served at root and that NextAuth endpoint `/api/auth/providers` returns valid JSON with the `keycloak` provider.
3. **`test_api_docs.sh`**:
   Fetches `/api/docs` and `/api/openapi.json`, verifying that Swagger UI loads and OpenAPI schema reflects API endpoints.
4. **`test_auth_keycloak.sh`**:
   Performs a live OIDC token exchange against Keycloak for `testuser` / `testpassword123`, fetches `/api/me` with the access token, and asserts `preferred_username == "testuser"`.
5. **`test_secret_lifecycle.sh`**:
   Executes end-to-end secret creation and one-time burning verification:
   - Creates an authenticated secret with TTL.
   - Retrieves ciphertext via `/api/secrets/reveal` (verifying 200 OK).
   - Attempts second retrieval to verify secret is burned (verifying 404 Not Found).
   - Repeats lifecycle for anonymous secret creation.

---

## 4. Prominent Pipeline Reporting

Upon successful deployment, the workflow surfaces the preview endpoints in three noticeable locations:

1. **GitHub Actions Step Summary (`$GITHUB_STEP_SUMMARY`)**:
   Renders a formatted Markdown table with direct links to the Web App, Swagger Docs, Health Check, and Keycloak Admin Console, along with test user credentials.
2. **Runner Console Banner**:
   Prints highlighted ASCII banner in the job build log.
3. **Sticky PR Comment**:
   Posts or updates a comment on the GitHub Pull Request containing clickable links and WebAuthn status.

---

## 5. Teardown (`cleanup-preview`)

Triggered automatically when a Pull Request is closed or merged:
- Connects to `staging-server` via Tailscale SSH.
- Tears down the preview container stack and removes ephemeral volumes (`docker compose down -v`).
- Removes the git worktree and deletes the local worktree branch.
- Cleans up `/etc/hosts` DNS entries on the staging host.
