# CI/CD & Preview Deployment Pipeline

SecretShare uses GitHub Actions for both CI testing and ephemeral preview deployments over Tailscale.

---

## 1. Test API Workflow (`.github/workflows/test-api.yml`)

Runs on pull requests and pushes to `main`, `develop`, and `feat/**`.

### Two Jobs:
1. **`test` (API & Frontend Unit Tests)**:
   - Sets up Python 3.12.
   - Runs `python -m pytest -q -m "not integration"`.
   - Executes `api/tests/test_frontend_and_routing.py` to validate static asset contracts, Node.js JS syntax (`node -c`), and PKCE fallback challenge calculation.
2. **`oauth-integration` (Live Docker Integration Tests)**:
   - Starts the full local Docker Compose stack (`db`, `keycloak`, `traefik`, `web`, `api`).
   - Verifies path routing via curl (`/`, `/api/health`, `/keycloak/realms/secretshare`).
   - Executes live integration tests against the running containers (`api/tests/test_oauth_integration.py`).

---

## 2. Preview Deployment Workflow (`.github/workflows/deploy-preview.yml`)

Deploys an ephemeral preview environment for every Pull Request.

### Prerequisites & Infrastructure:
- Connects to Tailscale network using `tailscale/github-action@v2` with `TS_OAUTH_CLIENT_ID` and `TS_OAUTH_SECRET`.
- Deploys via SSH directly to `staging-server` as `root`.
- Manages git worktrees in `/opt/secretshare/worktrees/pr-${PR_NUM}`.

### Self-Healing Deployment Strategy:
```bash
if ! docker compose -p "pr-${PR_NUM}" -f docker-compose.preview.yml up -d --build --remove-orphans; then
  echo "Initial compose up failed, resetting stale volumes and retrying..."
  docker compose -p "pr-${PR_NUM}" -f docker-compose.preview.yml down -v --remove-orphans || true
  docker compose -p "pr-${PR_NUM}" -f docker-compose.preview.yml up -d --build --remove-orphans
fi
```

### The 9-Step Automated Smoke Test Battery:
Before reporting success, the deployment script executes an exhaustive 9-step test on the live stack:
1. **Trailing-Slash Redirect**: `curl http://127.0.0.1/pr-${PR_NUM}` &rarr; checks for HTTP 301, 308, or 200.
2. **Frontend HTML Check**: Verifies `#login-btn` and `#create-btn` exist in the served HTML.
3. **Static JS Asset Delivery**: Verifies `/pr-${PR_NUM}/app.js` returns 200 OK and contains expected OAuth logic.
4. **API Swagger & OpenAPI Schema**: Verifies `/pr-${PR_NUM}/api/docs` and `/pr-${PR_NUM}/api/openapi.json`.
5. **Keycloak OIDC & Live Token Exchange**: Obtains an OAuth access token for `testuser` from the ephemeral Keycloak.
6. **Protected `/api/me` Verification**: Calls `/pr-${PR_NUM}/api/me` with Bearer token, verifies `preferred_username == "testuser"`.
7. **Negative Auth Tests**: Verifies 403 when unauthenticated and 401 on malformed tokens.
8. **Authenticated Secret Lifecycle**: Creates secret with Bearer token, retrieves it, and verifies 404 burn on second retrieval.
9. **Anonymous Secret Lifecycle**: Creates secret anonymously, retrieves it, and verifies 404 burn on second retrieval.

### Teardown:
When a pull request is closed or merged, `cleanup-preview` runs:
- Destroys containers and removes persistent volumes (`down -v`).
- Prunes the worktree directory (`git worktree remove --force`).
