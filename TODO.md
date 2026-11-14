# TODO — Partial / Missing Items

Source: `AUDIT_REPORT.md` (2026-11-14). Only ⚠️/❌ items. Sorted by marks at stake: CI/CD & tests first.
Effort: **S** ≈ 1–2 h · **M** ≈ half a day · **L** ≈ 1+ day. (Points for balancing: S = 1, M = 2, L = 3.)

**Progress:** 4 / 20 tasks done (6 / 29 points) — T8, T9, T10, T11 (Member 4 area), modified by Ecaterina on 2026-11-14, branch `chore/config-env-resilience`.

---

## P1 — CI/CD & Testing (10 marks)

### T1 · Publish test reports and coverage — S
Results only exist in Actions logs today; no JUnit, no coverage, no artifacts.
- **Files:** `.github/workflows/test-api.yml`, `.github/workflows/test-tls.yml`, `api/requirements-dev.txt` (add `pytest-cov`)
- **Accept:** each pytest step writes `--junitxml` + `--cov=app --cov-report=xml --cov-report=term`; `actions/upload-artifact` uploads them with `if: always()`; a coverage % and pass/fail table appear in `$GITHUB_STEP_SUMMARY`; a failing test still fails the job.

### T2 · Add a web CI job (build + CSP tests) — M
`web/tests/security/csp.test.mjs` passes locally (10/10) but no workflow runs it; the web build is only implicit inside compose.
- **Files:** new `.github/workflows/test-web.yml`
- **Accept:** on push/PR: `bun install --frozen-lockfile` → `bunx tsc --noEmit` → `bun run build` → start the production server → `CSP_TEST_URL=… node --test tests/security/`; job fails if any step fails; test output uploaded as an artifact.

### T3 · Frontend unit tests for the crypto layer — M
`web/lib/crypto.ts` (core E2E encryption) has zero tests.
- **Files:** new `web/tests/unit/crypto.test.*` (node:test or `bun test`, Node's built-in `crypto.webcrypto`), `web/package.json` (`test:unit` script)
- **Accept:** tests cover encrypt→decrypt round-trip, decrypt with the wrong private key fails, tampered ciphertext/IV fails (GCM tag), IV is 12 random bytes and differs per call; wired into T2's job.

### T4 · Lint / static checks in CI — S
`ruff check` reports 15 × F401 that CI never sees.
- **Files:** `.github/workflows/test-api.yml` (lint step), `api/requirements-dev.txt` (`ruff`), the affected `api/app`/`api/tests` files (remove unused imports)
- **Accept:** `ruff check app tests` exits 0 locally and runs as a CI step that fails the job on errors.
- **Status:** ⏳ Open. Side note: the unused `import ssl` in `api/app/main.py` was already removed during T11 (**modified by Ecaterina**); all files touched in T8–T11 pass `ruff check`.

### T5 · Enforce green CI before merge — S
PR #22 and #23 were merged with failing tests; 8 direct pushes to `main` (`a27bfae` broke CI).
- **Files:** GitHub repo settings (branch protection / ruleset on `main`); `README.md` CI section (document it); evidence screenshot in `docs/security/evidence/`
- **Accept:** `main` requires PRs and the checks `Run API tests`, `Run OAuth live integration tests`, `Run TLS tests`, plus the T2/T7 jobs; a direct push to `main` is rejected; screenshot committed.

### T6 · Fix or retire the staging deploy — M
`deploy-staging.yml` failed 2/2 runs (step "Deploy via Tailscale SSH"), never green.
- **Files:** `.github/workflows/deploy-staging.yml`
- **Accept:** one successful `workflow_dispatch` run on `main`, ending with a post-deploy smoke step (`curl -f …/api/health` + `test_web_routing.sh`); run URL linked in README. If staging is dropped, remove the workflow and the README section instead and say why.

### T7 · Secret scanning + dependency audit in CI — S
CLAUDE.md invariant 8 promises Gitleaks; CI has none. No SCA either.
- **Files:** new `.github/workflows/security.yml` (or a job in `test-api.yml`)
- **Accept:** `gitleaks` scans full history on every PR and fails on findings; `pip-audit -r api/requirements.txt` and `bun audit`/`npm audit --omit=dev` run and report; first clean run linked as evidence in `docs/security/evidence/`.

---

## P2 — Project readiness, config & environment

### T8 · Make the README production path work out of the box — S · ✅ DONE
Verified bug: `cp .env.example .env` → API healthy but every secret call returns 503 (`.env.example:24` uses `redis://` against TLS-only Redis). README prod path also omits `docker network create traefik-net`.
- **Files:** `.env.example`, `README.md` (§ Production / Staging)
- **Accept:** `REDIS_URL` in `.env.example` is `rediss://redis:6379/0` or removed; README prod steps include the network command; following the README verbatim on a clean clone gives a working create → reveal round-trip (record the commands + output).
- **Status:** ✅ Done — **modified by Ecaterina**.
  - Modified: `.env.example` (`REDIS_URL` commented out, defaults to `rediss://`; comment on TLS-only Redis), `README.md` (Production / Staging vs. Development section with `init-env.sh` + `traefik-net` steps; `REDIS_URL` row).
  - Verified: `.env` generated from `.env.example` → `docker compose up --build --wait` healthy in 44 s, API got `REDIS_URL=rediss://redis:6379/0`, `test_secret_lifecycle.sh` (create → exists → reveal → burn) exit 0.

### T9 · Remove insecure fallback secrets from compose — S · ✅ DONE
`AUTH_SECRET:-default_dev_auth_secret…` (`docker-compose.yml:42`, `docker-compose.preview.yml:41`), `POSTGRES_PASSWORD:-secretshare`, `KEYCLOAK_ADMIN_PASSWORD:-admin` (preview).
- **Files:** `docker-compose.yml`, `docker-compose.preview.yml`, `.env.example` (add `AUTH_SECRET=` placeholder + generation hint), `README.md` (credential section)
- **Accept:** secrets use `${VAR:?VAR must be set}`; `docker compose config` fails with a clear message when one is missing; preview workflow still green (it already generates them); README no longer claims `admin`/`secretshare` defaults.
- **Status:** ✅ Done — **modified by Ecaterina**.
  - Modified: `docker-compose.yml`, `docker-compose.preview.yml` (`${VAR:?…}` for `AUTH_SECRET`, `POSTGRES_PASSWORD`, `KEYCLOAK_ADMIN_PASSWORD`; all `:-secretshare` / `:-admin` fallbacks removed), `.env.example` (`AUTH_SECRET` placeholder, header pointing to the script), `README.md` (Quick Start step, credentials and env table say **required**), `.github/workflows/test-api.yml` (OAuth job now writes a random `AUTH_SECRET`).
  - Added: `scripts/init-env.sh` — creates `.env` from `.env.example` with distinct random values, mode 600, never prints them, refuses to overwrite.
  - Verified: empty env → `docker compose config` exit 1 with `… must be set in .env (run scripts/init-env.sh)` for both compose files; generated env → config OK.
  - Still open: PR preview pipeline not re-run (needs the Tailscale server). Staging server's `.env` must contain `AUTH_SECRET` before the next staging deploy.

### T10 · Real dev/prod separation — M · ✅ DONE
`ENVIRONMENT` is never set in compose, so the production fail-fast guard (`config.py:112`) never runs; Keycloak runs `start-dev` on staging; realm `sslRequired: none`.
- **Files:** `docker-compose.yml` (prod-like: `ENVIRONMENT=production`, Keycloak `start` + proxy/hostname settings), new `docker-compose.dev.yml` or `compose.override.yml` (dev conveniences), `.env.example`, `README.md`
- **Accept:** staging/prod stack runs with `ENVIRONMENT=production` and Keycloak in production mode; dev stack is one documented command; a test or CI step proves the API refuses to start in production with a missing setting.
- **Status:** ✅ Done — **modified by Ecaterina**.
  - Modified: `docker-compose.yml` (api `ENVIRONMENT=production`; Keycloak `start --import-realm` + `KC_PROXY_HEADERS=xforwarded`), `.env.example` (explains `ENVIRONMENT` is set per compose file), `README.md` (prod vs. dev commands, `ENVIRONMENT` row).
  - Added: `docker-compose.dev.yml` (override: `ENVIRONMENT=development`, Keycloak `start-dev`). Dev command: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build`.
  - Verified: prod stack — all 4 CI smoke scripts, 5 live OAuth tests, 10 web CSP tests pass; browser login (auth code + PKCE via NextAuth) simulated with curl → session `testuser`; blank `KEYCLOAK_REALM` → API exits 1 with `missing required settings for production: keycloak_realm`; with the dev override it starts. Unit test: `api/tests/test_config.py::test_production_requires_datastores_and_oidc`.
  - Left for Member 3 (T13): realm `sslRequired: none`. `docker-compose.preview.yml` still uses `start-dev` (untested pipeline, left unchanged).

### T11 · Explicit timeouts and resource limits — M · ✅ DONE
No explicit timeouts on Redis, Postgres, JWKS fetch or browser `fetch`; no limits on `api`.
- **Files:** `api/app/main.py` (Redis `socket_timeout`, `socket_connect_timeout`), `api/app/db/session.py` (`pool_timeout`, asyncpg `command_timeout`), `api/app/core/auth.py` (`PyJWKClient(timeout=…)`), `api/app/core/config.py` (settings for them), `web/app/page.tsx` (`AbortSignal.timeout`), `docker-compose.yml` (`deploy.resources.limits` for `api`)
- **Accept:** values configurable via settings; unit test shows a hung Redis call ends in 503 within the configured time; web shows a timeout error instead of hanging.
- **Status:** ✅ Done — **modified by Ecaterina**.
  - Modified: `api/app/core/config.py` (6 settings: `REDIS_CONNECT_TIMEOUT_SECONDS`=3, `REDIS_SOCKET_TIMEOUT_SECONDS`=5, `DB_CONNECT_TIMEOUT_SECONDS`=5, `DB_COMMAND_TIMEOUT_SECONDS`=10, `DB_POOL_TIMEOUT_SECONDS`=10, `JWKS_TIMEOUT_SECONDS`=5), `api/app/storage/redis_store.py` (new `create_redis_client()`), `api/app/main.py` (uses it + passes DB timeouts), `api/app/db/session.py` (asyncpg `timeout`/`command_timeout`, `pool_timeout`), `api/app/core/auth.py` (`PyJWKClient(timeout=…)`), `web/app/page.tsx` (`apiFetch()` with 60 s `AbortSignal.timeout` on all 5 API calls, friendly timeout message), `docker-compose.yml` (api limit 1 CPU / 512 MB), `api/tests/test_config.py` (new env names in the clean-env list), `.env.example` + `README.md` (documented).
  - Added: `api/tests/test_timeouts.py` (11 tests, incl. hung Redis → `503` + `Retry-After` in < 3 s).
  - Verified: full API suite 187 passed / 5 skipped, security 61/61, TLS 18/18; negative control — same hung socket without timeout still blocked after 5 s; api container limits confirmed with `docker inspect`; web image builds (`next build` type-check).
  - Why 60 s in the browser: the slowest reveal path (rate limit + JWKS + burn + audit write) can reach ≈ 40 s with the API defaults; aborting a reveal the server already completed would burn the secret.

---

## P3 — Security & quality

### T12 · Verify the token issuer — S
`jwt.decode` checks signature + audience but not `iss` (`api/app/core/auth.py:53-57`).
- **Files:** `api/app/core/auth.py`, `api/app/core/config.py` (`keycloak_issuer`, because the public issuer URL differs from the internal `KEYCLOAK_URL`), compose files, `api/tests/security/test_auth_error_disclosure.py`
- **Accept:** a token with a foreign `iss` gets 401 with the generic message; new test passes; live OAuth integration test still green.

### T13 · Harden the Keycloak realm — M
`redirectUris: ["*", …]`, `directAccessGrantsEnabled: true`, no brute-force protection, `sslRequired: none` (`keycloak/realm-export.json`).
- **Files:** `keycloak/realm-export.json`, `.github/workflows/deploy-preview.yml:155,166-169` (its `sed`/SQL depend on the wildcard), test scripts that use the password grant
- **Accept:** explicit redirect URIs per environment; brute-force detection on; `sslRequired: external` where TLS exists; password grant either disabled or limited to a separate test client; preview + OAuth CI jobs still green.

### T14 · Close the Traefik dashboard — S
`--api.insecure=true` + published `:8080` (`docker-compose.yml:5,12`, `deploy-preview.yml:85,89`); verified reachable.
- **Files:** `docker-compose.yml`, `.github/workflows/deploy-preview.yml`, `README.md:41`
- **Accept:** dashboard disabled or bound to `127.0.0.1` only; `curl <host>:8080/api/rawdata` from another host fails; README matches reality.

### T15 · Authorization gaps + roles decision — M
`GET /keys/{user_id}` is unauthenticated → user enumeration (`api/app/api/routes/keys.py:50-54`). No roles anywhere.
- **Files:** `api/app/api/routes/keys.py`, `web/app/page.tsx` (send the token), `api/tests/test_keys.py`; decision written in `api/docs/security/security-controls.md`
- **Accept:** endpoint requires a valid token (401 otherwise) with a test; either a Keycloak realm role is enforced for an admin-only route **or** a documented rationale for resource-based authorization (recipient-bound burn) instead of RBAC.

---

## P4 — Logging, health, documentation & exam prep

### T16 · Proper application logging — M
No logging config in the API process (`basicConfig` only in `api/app/db/migrate.py:53`); app lines lack level/time; INFO dropped; `/secrets/exists` over-redacted.
- **Files:** new `api/app/core/logging_config.py`, `api/app/main.py`, `api/app/core/config.py` (`log_level`), `api/app/core/logging_filters.py` (exclude `exists`), request-ID middleware, `api/tests/security/test_access_log.py`
- **Accept:** every log line has timestamp, level, logger, request id; `LOG_LEVEL` env works; redaction filter still applied (existing 9 tests green + a test that `/secrets/exists` is not redacted).

### T17 · Readiness endpoint — S
`/health` returns 200 while Redis is down (verified).
- **Files:** `api/app/main.py` (`/health/ready` pinging Redis + `SELECT 1`), `api/tests/test_api.py`, compose healthcheck / `api/Dockerfile` (decide which probe uses which), `README.md`
- **Accept:** `/health` = liveness (always 200); `/health/ready` returns 503 with per-dependency status when Redis or Postgres is down, 200 otherwise; tests for both cases.

### T18 · README: design decisions, trade-offs, known limitations, security improvements — M
Rationale is scattered across code comments, `context/`, `api/docs/`; README has none of it.
- **Files:** `README.md` (new sections), optionally `docs/adr/000x-*.md`
- **Accept:** README has: *Design decisions & trade-offs* (modular monolith, Keycloak vs custom auth, Redis + Lua atomic burn, ID in body not path, fail-open rate limiter, audit "availability over completeness", Traefik path routing); *Known limitations* (extractable private key, no `iss` check if not fixed, metadata visible to server, served-JS trust problem, staging status); *Security improvements* linking AUD-6 and CSP evidence; *Test reports* (where to find T1 artifacts); test instructions mention `TEST_DATABASE_URL`/`TEST_REDIS_URL` and the web tests.

### T19 · Fill the empty API contract — S
`api/docs/architecture/api-contract.md` is 0 lines.
- **Files:** `api/docs/architecture/api-contract.md`
- **Accept:** every route (method, path, auth, request/response, error codes, rate limit) listed and matching `/api/openapi.json`; or the file is deleted and README points to Swagger.

### T20 · Merge the pending docs branch — S
`docs/security-documentation` is 4 commits ahead of `origin/main` and not on `main`.
- **Files:** none new (PR from the local branch)
- **Accept:** commits `40b7835`, `5cdb489`, `ac81f0d`, `907eea5` merged to `main` via PR with green checks.

---

**Total: 11 × S + 9 × M = 11 + 18 = 29 points** (≈ 6 per team member).
