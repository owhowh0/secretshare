# CI/CD & Deployment

Four GitHub Actions workflows live in `.github/workflows/`. Tests and preview deploys run on every PR. Staging is manual.

| Workflow | Trigger | What it does |
| :--- | :--- | :--- |
| `test-api.yml` | PRs; pushes to `main`, `develop`, `feat/**` | Unit, security and integration tests |
| `test-tls.yml` | same | `tests/test_tls.py` only |
| `deploy-preview.yml` | PR opened / synchronize / reopened / closed | Per-PR preview on `staging-server` plus the smoke battery; teardown on close |
| `deploy-staging.yml` | **`workflow_dispatch` only**, on `main` | Rebuilds `docker-compose.yml` as project `staging`. **Currently broken** (troubleshooting §13). |

---

## 1. `test-api.yml`

### Job `test` (Run API tests)
- Python 3.12, `pip install -r requirements.txt -r requirements-dev.txt` (pip, not uv).
- Service containers: `postgres:16` and `redis:7`, with `DATABASE_URL`, `TEST_DATABASE_URL` and `TEST_REDIS_URL` pointing at them.
- `python -m alembic upgrade head`, then `python -m pytest -q --strict-markers --ignore=tests/test_tls.py`.
- **Skip gate:** runs `pytest tests/security` again and fails if anything was skipped. The security suites skip themselves without Redis or Postgres, and the gate stops CI from going green without asserting the invariants.

### Job `oauth-integration` (Run OAuth live integration tests)
- Generates a throwaway `.env` and runs `docker compose up -d --wait db keycloak traefik web api` (the local `docker-compose.yml`).
- Runs `test_web_routing.sh`, `test_api_docs.sh`, and a realm check against `http://localhost:80`.
- Runs `pytest -m integration tests/test_oauth_integration.py`: a real Keycloak password grant for `testuser`, `/me`, tampered-token 401, and a full create → reveal → 404 lifecycle addressed to `testuser`.

## 2. `test-tls.yml`
Runs `python -m pytest tests/test_tls.py`: the `tls_ca_cert` setting, the SSL contexts for the engine and Redis, and the artefacts produced by `tls/generate.sh` (including `ca.srl`).

---

## 3. `deploy-preview.yml`

Runs only for PRs from this repository whose author is `OWNER`, `MEMBER` or `COLLABORATOR`.

### Deploy steps (remote script over `tailscale ssh root@staging-server`)
1. Ensure the shared `traefik-net` network and the global `traefik` container (ports :80/:8080, `forwardedHeaders.trustedIPs` = private ranges) exist. An older router without that flag is recreated.
2. Clone `/opt/secretshare` if needed, then sync the worktree `/opt/secretshare/worktrees/pr-<N>` to `pull/<N>/head`.
3. Write `.env`, reusing existing secrets if a `.env` is already there: `PR_NUMBER`, `POSTGRES_PASSWORD`, `KEYCLOAK_ADMIN_PASSWORD`, `AUTH_SECRET`, `TS_AUTHKEY`, `PR_HOSTNAME=pr-<N>.<tailnet>.ts.net`.
4. Patch `tailscale/serve.json` and the realm redirect URIs with the PR hostname.
5. Run `docker compose -p pr-<N> -f docker-compose.preview.yml up -d --build`. On failure it runs `down -v` and retries once.
6. Insert `https://<PR_HOSTNAME>/*` (and `*`) into Keycloak's `redirect_uris` via `psql`, because a persisted Keycloak DB skips the realm import.
7. Wait for the tailscale sidecar to reach `Running`, activate `tailscale serve` for :443 and :80, and add the node IP to the server's `/etc/hosts`.
8. Run the smoke battery against `https://<PR_HOSTNAME>` (§4).
9. Print `=== Preview deployment and all verification tests passed successfully! ===`.

After the SSH step, the job **greps `deploy.log` for that final line and fails if it's missing** (troubleshooting §9). Every `docker compose exec -T` in the heredoc must keep its `</dev/null`.

It then writes a step summary and posts or updates a sticky PR comment with the preview links.

### Teardown (`cleanup-preview`, on PR close)
`docker compose -p pr-<N> down -v`, remove the worktree and branch, and clean the `/etc/hosts` entry.

---

## 4. Smoke Battery (`.github/scripts/`)

All scripts take the base URL and use `curl -k`.

| Script | Checks |
| :--- | :--- |
| `wait_services_ready.sh` | Polls `/`, `/api/health` and `/keycloak/realms/secretshare` until all return 200. Dumps diagnostics on timeout. |
| `test_web_routing.sh` | HTML and Next.js asset delivery |
| `test_api_docs.sh` | `/api/health`, `/api/docs`, `/api/openapi.json` |
| `test_auth_keycloak.sh` | NextAuth providers, OIDC discovery, password grant for `testuser` (the token is saved for the next script), `/api/me`, 403 without a token, 401 with a bad token |
| `test_secret_lifecycle.sh` | (1) Recipient lifecycle: create for `testuser` → reveal 200 → second reveal 404. (2) **Denied reveals don't burn:** a secret addressed to `someone-else-e2e` gets 403 twice as `testuser`, `POST /api/secrets/exists` still says `true`, an unauthenticated reveal gets 401/403, and the secret still exists. (3) TTL: 3600 → 201 with `expires_at`; 10 and 86401 → 422. |

The scripts build envelopes with fixed dummy key material (the server never inspects it). When the create/reveal contract changes, update `envelope()` in `test_secret_lifecycle.sh`.

Rate limits are per client IP (10 creates per minute). All smoke requests come from the same runner, and the battery uses 5 creates.

---

## 5. `deploy-staging.yml`
Manual only, restricted to `main`. It syncs `/opt/secretshare` hard to `origin/main` (`fetch`, `checkout -B`, `reset --hard`, `clean -fd`) and runs `docker compose -p staging -f docker-compose.yml up -d --build`. It currently fails (missing `.env` and a Traefik port conflict; see troubleshooting §13).
