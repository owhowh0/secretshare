# CI/CD & Deployment

Five GitHub Actions workflows live in `.github/workflows/`. Tests, security audits, and preview deploys run on every PR. Staging is manual.

| Workflow | Trigger | What it does |
| :--- | :--- | :--- |
| `test-api.yml` | PRs; pushes to `main`, `develop`, `feat/**` | Ruff linting, unit/security tests, OAuth live tests, coverage & JUnit artifacts |
| `test-tls.yml` | same | `tests/test_tls.py` only, coverage & JUnit artifacts |
| `security.yml` | same | Gitleaks secret scan, `pip-audit` for API, `bun audit` for web |
| `deploy-preview.yml` | PR opened / synchronize / reopened / closed | Per-PR preview on `staging-server` plus the smoke battery; teardown on close |
| `deploy-staging.yml` | **`workflow_dispatch` only**, on `main` | Rebuilds `docker-compose.yml` as project `staging` on staging host with smoke verification |

---

## 1. `test-api.yml`

### Job `test` (Run API tests)
- Python 3.12, `pip install -r requirements.txt -r requirements-dev.txt` (including `ruff` and `pytest-cov`).
- **Lint step:** `ruff check app tests` (fails on unused imports or style errors).
- Service containers: `postgres:16` and `redis:7`, with `DATABASE_URL`, `TEST_DATABASE_URL` and `TEST_REDIS_URL` pointing at them.
- `python -m alembic upgrade head`.
- Runs pytest with `--junitxml=test-results/junit.xml --cov=app --cov-report=xml:test-results/coverage.xml --cov-report=term`.
- **Skip gate:** runs `pytest tests/security` again and fails if anything was skipped. The security suites skip themselves without Redis or Postgres, and the gate stops CI from going green without asserting the invariants.
- **Reporting & Artifacts:** uploads JUnit XML and Cobertura coverage XML as actions artifacts and appends pass/fail/coverage summary table to `$GITHUB_STEP_SUMMARY`.

### Job `oauth-integration` (Run OAuth live integration tests)
- Generates a throwaway `.env` and runs `docker compose up -d --wait db keycloak traefik web api` (the local `docker-compose.yml`).
- Runs `test_web_routing.sh`, `test_api_docs.sh`, and a realm check against `http://localhost:80`.
- Runs `pytest -m integration tests/test_oauth_integration.py` with JUnit and coverage collection.
- Publishes OAuth test summary to `$GITHUB_STEP_SUMMARY` and uploads artifacts.

## 2. `test-tls.yml`
Runs `python -m pytest tests/test_tls.py` with `--junitxml`, `--cov=app`, and uploads artifacts: the `tls_ca_cert` setting, the SSL contexts for the engine and Redis, and the artefacts produced by `tls/generate.sh` (including `ca.srl`).

## 3. `security.yml`
Runs on pushes and PRs:
- **Gitleaks (`gitleaks/gitleaks-action@v2`):** full history scan (`fetch-depth: 0`) against `.gitleaks.toml`.
- **pip-audit:** scans `api/requirements.txt` against PyPI/OSV vulnerability databases.
- **bun audit:** scans frontend dependencies in `web/bun.lock`.

---

## 4. `deploy-preview.yml`

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
Manual only, restricted to `main`. It syncs `/opt/secretshare` hard to `origin/main` (`fetch`, `checkout -B`, `reset --hard`, `clean -fd`), initializes `.env` via `scripts/init-env.sh` if missing, starts the stack with `docker compose -p staging up -d --build`, and executes post-deployment smoke verification (`wait_services_ready.sh`, `curl /api/health`, and `test_web_routing.sh`). All heredoc commands redirect stdin (`</dev/null`) to avoid hung execution.

---

## 6. Branch Protection & Merge Policies

Enforced on `main` to prevent broken builds and unreviewed changes:
- Direct pushes to `main` are rejected.
- All merges require a Pull Request with approved reviews.
- Mandatory status checks before merge:
  - `Run API tests`
  - `Run OAuth live integration tests`
  - `Run TLS tests`
  - `Secret scanning (Gitleaks)`
  - `Python dependency audit (pip-audit)`
  - `Frontend dependency audit (bun audit)`
- Strict linear history: branch must be up to date before merge.
- Evidence and reproduction documented in `docs/security/evidence/branch-protection-rules.md`.
