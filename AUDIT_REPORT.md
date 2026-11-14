# SecretShare — Final Exam Readiness Audit

Audit date: 2026-11-14. Audited tree: local branch `docs/security-documentation` at `907eea5`.
That is `origin/main` (`6a78ed2`, merge of PR #33) plus 4 docs/comment-only commits that are **not yet on `main`**
(`git rev-list --left-right --count origin/main...HEAD` → `1 4`; the only code-file diff is comments in `web/middleware.ts` and `web/next.config.ts`).

Legend: ✅ Done · ⚠️ Partial · ❌ Missing · **UNVERIFIED** = could not be checked from this machine.

---

## 1. What was actually run

All commands ran on the audit machine (Docker 29.9.3, Python 3.12.13, Node 26). Nothing in the repo was modified;
throwaway env files, venv and containers lived in a scratch directory and were removed afterwards.

| # | Command (from repo root unless noted) | Result |
|---|---|---|
| R1 | `docker run postgres:16` + `docker run redis:7` (same images as CI services) | healthy |
| R2 | `cd api && python -m alembic upgrade head` | 2 migrations applied (`02234c7da915`, `a1b2c3d4e5f6`) |
| R3 | `cd api && python -m pytest -q --strict-markers --ignore=tests/test_tls.py` (CI's exact command, with `DATABASE_URL`/`TEST_DATABASE_URL`/`TEST_REDIS_URL` set like CI) | **176 passed, 5 skipped** (the 5 = `test_oauth_integration.py`, need Keycloak) |
| R4 | `cd api && python -m pytest tests/security -q` (CI's skip-guard step) | **61 passed, 0 skipped** |
| R5 | `cd api && python -m pytest tests/test_tls.py -q --strict-markers` | **18 passed** |
| R6 | `docker compose -p auditss --env-file <tmp>.env up -d --build --wait` (`docker-compose.yml`, fresh random passwords) | **exit 0 in 96 s**; api + web images built; all 7 services healthy |
| R7 | `bash .github/scripts/test_web_routing.sh http://localhost:18080 false` / `test_api_docs.sh` / `test_auth_keycloak.sh` / `test_secret_lifecycle.sh` | all **exit 0** |
| R8 | `REQUIRE_KEYCLOAK=1 … pytest -m integration tests/test_oauth_integration.py` against R6 stack | **5 passed** |
| R9 | `cd web && CSP_TEST_URL=http://localhost:18080 node --test tests/security/` | **10 passed, 0 failed** (not run in CI — see 2.4) |
| R10 | `curl` probes: 200 KB body → `POST /api/secrets` | **413** |
| R11 | 35 × `POST /api/secrets/exists` | 21 × 200, then **429** |
| R12 | `docker compose stop redis`, then `GET /api/health` and `POST /api/secrets` | health **200 `{"status":"ok"}`**; create **503** "Secret storage is temporarily unavailable" |
| R13 | `docker compose logs api` after R7–R12, grep for `eyJ`, `Bearer`, `ciphertext` | **0 hits**; id-bearing paths show as `/secrets/<redacted>` |
| R14 | `cp .env.example` → fill passwords only → `docker compose up tls-init db redis api` (README "Production / Staging" path) | api **healthy**, but `POST /secrets` → **503**: `REDIS_URL=redis://redis:6379/0` from `.env.example:24` points plain TCP at a TLS-only Redis (`docker-compose.yml:159` `--port 0`) |
| R15 | `uvx ruff@0.8.4 check app tests` (not part of CI) | 15 × F401 unused-import |
| R16 | GitHub REST API `GET /repos/owhowh0/secretshare/actions/runs` (public, 405 runs) | Test API 20 ✅ / 9 ❌, Test TLS 29 ✅, PR Preview 21 ✅ / 1 ❌, **Deploy Staging 0 ✅ / 2 ❌** |
| R17 | `git grep` + `git log --all -p` regex sweep for secrets (see 2.1) | no real credentials found |
| R18 | Attempted `gitleaks` (Docker) over full history | **not run** — blocked by the audit environment's permission policy. History scan is regex-only. |

---

## 2. Requirement-by-requirement

### 2.1 Project readiness

| Requirement | Status | Evidence | Notes |
|---|---|---|---|
| Fully implemented | ✅ | R6–R9 pass end-to-end: login (Keycloak), key registration, create → exists → reveal → burn. `api/app/api/routes/secrets.py:57,93,110`, `web/lib/crypto.ts`, `web/app/page.tsx` | `api/docs/architecture/api-contract.md` is **0 lines** (empty stub). |
| Deployed (local / cloud / container) | ✅ | Containerised: `api/Dockerfile`, `web/Dockerfile`, `docker-compose.yml`; R6 stack up. CI PR previews on a Tailscale server: 21 successful `PR Preview Deployment` runs (R16), latest `35884715312` on 2026-09-23. | Permanent staging (`deploy-staging.yml`) failed **2/2** runs (`35624623507`, `35628450170`, step "Deploy via Tailscale SSH") and has not been re-run. Whether the server is up today is **UNVERIFIED** (private tailnet). |
| Runs without manual fixes | ⚠️ | R6: `docker-compose.yml` with a complete env file → zero fixes. R14: README's own path (`README.md:89-95`, `cp .env.example .env`) → API silently broken (503) because of `.env.example:24`. | Also, the Production section of the README omits `docker network create traefik-net`, which `docker-compose.yml:251-254` requires (`external: true`). Not reproduced (network already existed on the audit machine), but Compose refuses to start with a missing external network. |
| No hard-coded secrets | ⚠️ | No real credentials in tree or history (R17; only `.env.example` was ever added among env/key files: `git log --all --diff-filter=A`). `.env` git-ignored (`.gitignore:2-4`) and never committed. | Insecure **fallback defaults** in compose: `AUTH_SECRET=${AUTH_SECRET:-default_dev_auth_secret_must_be_32_characters}` (`docker-compose.yml:42`, `docker-compose.preview.yml:41`); `POSTGRES_PASSWORD:-secretshare` (`docker-compose.preview.yml:85,141`); `KEYCLOAK_ADMIN_PASSWORD:-admin` (`docker-compose.preview.yml:231`). Demo user password `testpassword123` in `keycloak/realm-export.json:83`, `README.md:105`, `.github/workflows/test-api.yml:134`, and printed in PR comments (`deploy-preview.yml:228,259`). CI's `POSTGRES_PASSWORD: secretshare` (`test-api.yml:27,48`) is an ephemeral service container — acceptable. |

### 2.2 CI/CD & testing (10 marks)

| Requirement | Status | Evidence | Notes |
|---|---|---|---|
| Pipeline builds automatically | ✅ | `test-api.yml` runs on every push to `main`/`develop`/`feat/**` and every PR (`:3-9`); installs deps, runs migrations; the `oauth-integration` job builds both Docker images via `docker compose up -d --wait db keycloak traefik web api` (`:119`). `deploy-preview.yml` builds per PR. | Build of the web app is only implicit (inside compose). No lint/type-check step (R15 shows 15 lint errors CI never sees). |
| Runs automated tests | ✅ | `test-api.yml:70` (pytest), `:72-80` (fails if any security test skipped), `:121-140` (routing smoke + live OAuth tests); `test-tls.yml:35`; preview E2E scripts `deploy-preview.yml:196-202`. | |
| Fails when tests fail | ✅ | R16: 9 failed `Test API` runs, most at step **"Run tests"** (e.g. `35603690360`, `35624623486`); preview job fails unless the final success line is printed (`deploy-preview.yml:207-210`). | **But a red pipeline did not stop merges**: PR #22 (`30741ca`) and PR #23 (`b996ac5`) landed on `main` with failing "Run tests"; `a27bfae` was pushed straight to `main` and broke CI (`35844926994`). 8 of 33 first-parent commits on `main` are direct pushes. Branch protection settings are **UNVERIFIED** (need repo admin), but the history shows it was not enforced. |
| Unit + integration tests | ✅ | 181 Python tests in 14 modules (R3 + R8). Unit: `test_config.py` (24), `test_proxy.py` (24), `test_secrets.py` (33, uses `tests/fakes.py`). Integration: DB-backed `tests/security/test_audit_db.py`, `test_audit_route_db.py`, `test_migrate.py`; live Keycloak `test_oauth_integration.py`; shell E2E `.github/scripts/test_*.sh`. TLS: 18. | Frontend has **no unit tests** (crypto in `web/lib/crypto.ts` is untested). `web/tests/security/csp.test.mjs` exists and passes (R9) but **is not run in any workflow** (`grep -r "node --test" .github` → nothing). No coverage measurement (`pytest-cov` absent from `api/requirements-dev.txt`). |
| Test results / reports available | ⚠️ | Results visible only in Actions logs. `grep -rn "upload-artifact\|junit" .github/workflows` → nothing. Preview job writes a step summary of links only (`deploy-preview.yml:218-230`). | No JUnit XML, no coverage report, no artifacts. |

**Estimated CI/CD score: 7.5 / 10.**
Full marks for build-on-push, automated tests, fail-on-failure and unit+integration coverage of the backend.
Lost: no published test reports/coverage (−1), web tests and web build/lint not in CI (−1), red CI merged to `main` / no enforced checks, staging deploy never green (−0.5).

### 2.3 Version control, config, README, errors & logging

| Requirement | Status | Evidence | Notes |
|---|---|---|---|
| Meaningful commit messages | ✅ | 161 of 175 non-merge commits on `main` follow Conventional Commits (`feat(api): …`, `fix(tls): …`). | 14 weak ones, e.g. `update context` (`13c76d3`), `allow external network` (`60c6322`), `add README`. |
| Logical history (not one commit) | ✅ | 207 commits on `main`, 2026-09-09 → 2026-09-23, 10 author identities. | |
| Branches / PRs | ✅ | 25 PR merges on `main`'s first-parent line (PR #1 … #33); 11 local branches (`git branch -a`). | 8 direct pushes to `main` (see 2.2). 4 local docs commits not yet merged. `gh` CLI not installed, so PR review/approval data is **UNVERIFIED**. |
| Separate dev / prod config | ⚠️ | `api/app/core/config.py`: `environment: development\|testing\|production`, and production fails fast if DB/Keycloak settings are missing (`:112`). Separate compose files: `docker-compose.yml` (local/staging) vs `docker-compose.preview.yml` (per-PR). | `ENVIRONMENT` is **never set** in either compose file → the production guard never runs in a deployment. Keycloak runs `start-dev` everywhere, including staging (`docker-compose.yml:210`). Realm has `"sslRequired": "none"` (`keycloak/realm-export.json:6`). No dev override / prod profile. |
| Secure env-variable handling | ⚠️ | Single source of config via pydantic-settings (`config.py:22`); `.env` ignored and never committed; CI uses GitHub Secrets (`deploy-preview.yml:27-35`); preview passwords randomised per PR (`deploy-preview.yml:121-123`). | Fallback secrets in compose (2.1); broken `REDIS_URL` in `.env.example:24` (R14). |
| README: description | ✅ | `README.md:1-27` | |
| README: setup / run | ⚠️ | `README.md:66-95` | Production path broken (R14) and misses the `traefik-net` step. States Keycloak admin defaults to `admin` (`:113`), but `docker-compose.yml` has no default for it. Says Traefik dashboard is "Internal only" for previews (`:41`) while `deploy-preview.yml:85,89` publishes `:8080` with `--api.insecure=true`. |
| README: how to run tests | ⚠️ | `README.md:181-200` | Does not say to set `TEST_DATABASE_URL`/`TEST_REDIS_URL`, so following `:186` locally skips the DB-backed security tests without warning. Web CSP tests not mentioned. |
| README: CI/CD overview | ✅ | `README.md:204-218` | |
| README: architecture | ✅ | Routing table + topology diagram `README.md:31-62`; deeper docs in `context/01_architecture_and_routing.md`, `api/docs/architecture/crypto-spec.md`, `data-model.md`. | No "design decisions / trade-offs" or "known limitations" section in the README (see 2.6). |
| Proper error handling | ✅ | Domain exceptions → 404/403/422/503 with `Retry-After` (`api/app/api/errors.py:41-43`); single not-found message for unknown/burned/expired (no enumeration oracle); 422 never echoes input (`errors.py:59`); global 500 handler (`api/app/main.py:120-129`); web shows user-facing errors (`web/app/page.tsx:117-157,282-318`). Verified R10, R12. | |
| Meaningful logs | ⚠️ | Audit trail to Postgres (`api/app/core/audit.py`); warnings for rejected tokens and rate-limiter fallback seen in R12 logs. | **No logging configuration in the API process.** `basicConfig` exists only in `api/app/db/migrate.py:53`, a separate process. App warnings printed without level/timestamp/logger name (e.g. `Token rejected: DecodeError: Not enough segments`) and `INFO` from `secretshare.*` loggers is dropped. No request IDs, no `LOG_LEVEL`. |
| No sensitive data in logs | ✅ | R13: 0 tokens/ciphertext in container logs. Payload id moved from path to body (AUD-6), path redaction filter (`api/app/core/logging_filters.py:16`), audit stores 8-char id prefix only (`audit.py`), tests `api/tests/security/test_access_log.py` (9), `test_auth_error_disclosure.py` (13). | Cosmetic: the redaction regex also redacts the fixed route `/secrets/exists` (seen as `POST /secrets/<redacted>` in R13). |

### 2.4 Security & quality

| Requirement | Status | Evidence | Notes |
|---|---|---|---|
| Input validation | ✅ | Pydantic bounds: `recipient_id` ≤ 255, `iv` ≤ 64, ciphertext ≤ 64 KB in bytes, `payload_id` ≤ 128, TTL min/max (`api/app/schemas/secrets.py:27-77`); PEM regex + platform allowlist (`api/app/schemas/keys.py:7,40`); raw-ASGI body limit before parsing (`api/app/core/limits.py`). R10 → 413, R7 → out-of-range TTL 422. | `encrypted_keys` list has no max item count (bounded only by body size). |
| Secure authentication | ⚠️ | Keycloak OIDC + PKCE (NextAuth, `web/auth.ts`); API validates RS256 JWT via JWKS with audience check (`api/app/core/auth.py:53-57`); uniform 401 message (`auth.py:19`). | `iss` claim **not verified** (`jwt.decode` has no `issuer=`). Realm: `redirectUris: ["*", …]` (`realm-export.json:38-39`), `directAccessGrantsEnabled: true` (`:20`, password grant), no `bruteForceProtected`, `sslRequired: none`. Keycloak `start-dev`. Browser private key generated **extractable** (`web/lib/crypto.ts:36`). Traefik dashboard open with `--api.insecure=true` (`docker-compose.yml:5`; R6 probe `GET :18081/api/rawdata` → 200). |
| Authorization / roles | ⚠️ | Resource-level authorization: only the bound recipient can reveal, enforced atomically in a Redis Lua script; a denied caller does **not** burn the secret (`api/app/storage/redis_store.py:13-22`; tests in `tests/security/test_secrets_invariants.py`). Reveal/register need a token (`routes/secrets.py:118`, `routes/keys.py:18`). | No roles/RBAC anywhere (`grep -rn "roles\|realm_access" api/app web` → nothing). `GET /keys/{user_id}` is **unauthenticated** (`api/app/api/routes/keys.py:50-54`) → anyone can enumerate which users have registered devices. `POST /secrets` is unauthenticated (by design, rate-limited). |
| ≥1 documented security improvement (risk + verification) | ✅ | **AUD-6**: payload id leaked into access logs → moved to request body + log filter; before/after log capture in `api/docs/security/evidence/aud-6-access-log.md`, regression tests `api/tests/security/test_access_log.py`; re-confirmed by R13. **WEB-1 CSP**: nonce + `strict-dynamic`; evidence `docs/security/evidence/csp-*.png/.txt`, test `web/tests/security/csp.test.mjs` (R9). Plus threat model, risk register, IR plan in `api/docs/security/`. | Not linked from the README. |

### 2.5 Bonus

| Requirement | Status | Evidence | Notes |
|---|---|---|---|
| Health-check endpoint | ✅ | `GET /health` (`api/app/main.py:100-102`), Docker `HEALTHCHECK` (`api/Dockerfile:65`), compose healthchecks for db/redis/keycloak, CI/preview checks. | Liveness only: R12 shows **200 while Redis is down**. No readiness check of Redis/Postgres. |
| Timeouts / limits | ⚠️ | Limits: 64 KB body (R10), per-IP rate limit (R11, `api/app/core/rate_limit.py`), TTL bounds, CPU/mem limits on `web` (`docker-compose.yml:52-56`). | **No explicit timeouts**: `Redis.from_url` (`api/app/main.py:41`) and `create_async_engine` (`api/app/db/session.py:19`) use library defaults; web `fetch` calls have no `AbortSignal` timeout; no resource limits on `api`. |
| Graceful failure handling | ✅ | Redis outage → 503 + `Retry-After` (R12); audit-write failure logged and swallowed (`api/app/core/audit.py:72-73`); rate limiter fails open with a warning (`rate_limit.py:53`); production config fails fast (`config.py:112`); `pool_pre_ping=True`. | Fail-open rate limiting is a deliberate availability-over-protection trade-off; be ready to defend it. |

### 2.6 Exam readiness

| Requirement | Status | Evidence | Notes |
|---|---|---|---|
| Design decisions & trade-offs explainable | ⚠️ | Rationale exists but is scattered: code comments (e.g. `redis_store.py:1-12`, `limits.py`, `audit.py` "availability over audit completeness"), `context/*.md`, `api/docs/architecture/crypto-spec.md`, `api/docs/security/threat-model.md`. | No single ADR / "Design decisions" section to revise from. |
| Known limitations documented | ⚠️ | Residual risks in `api/docs/security/risk-register.md` (e.g. R-02 extractable key, referenced at `README.md:163`). | Not summarised in the README; several live limitations found here (no `iss` check, open Traefik dashboard, `start-dev`, staging deploy broken, key-enumeration endpoint) are not listed together anywhere a grader would look. |

---

## 3. Scores

| Section | Estimate |
|---|---|
| CI/CD & Testing | **7.5 / 10** |
| Overall readiness | **≈ 78 %** — 15 ✅, 12 ⚠️, 0 ❌ across 27 checklist rows (✅ = 1, ⚠️ = 0.5) |

Fastest gains: publish test reports + run web tests in CI (CI marks), fix `.env.example`/README production path (readiness), remove compose secret fallbacks, add a readiness check and a "Design decisions & known limitations" README section.

---

## 4. Self-Evaluation

**Overall scan quality: 8 / 10.**

**Checked thoroughly (high confidence):**
- Build and tests: actually executed — CI-equivalent pytest (176 + 18 + 5), all four smoke scripts, the web CSP suite, and a full `docker compose` build/run. Results above are observed, not inferred.
- CI behaviour: every workflow file read line by line; outcomes and failing steps of all 405 runs pulled from GitHub's public API.
- Runtime security properties: body limit, rate limit, Redis-down behaviour, log contents, response headers, Traefik dashboard exposure — probed live.
- The `.env.example` Redis bug: reproduced, not guessed.
- Git history: commit counts, conventional-commit ratio, merges vs direct pushes, added-file history.

**Could not verify:**
- Live cloud/staging deployment (private Tailscale network; staging runs need repo auth to read logs, so the cause of the 2 failures is unknown).
- Branch-protection settings and PR review/approval data (needs repo admin / `gh` CLI, which is not installed).
- A dedicated secret scanner: `gitleaks` was blocked by the audit environment's permission policy. The history check is a regex sweep over `git log --all -p` (AWS/GitHub/Slack/Tailscale/OpenAI/private-key formats, `PASSWORD|SECRET|TOKEN|AUTHKEY=` literals). High-entropy strings without a known prefix could be missed.
- Browser-level behaviour of the E2E encryption (key generation, IndexedDB, decrypt) — exercised only indirectly through the API; no browser automation was run.
- The missing-`traefik-net` failure in the README production path (inferred from `external: true`; not reproduced).

**Possible false positives:**
- Demo credentials (`testuser/testpassword123`, CI's `secretshare` DB password) are flagged as hard-coded but are test-only and intentional; a grader may not penalise them.
- "No roles" may be acceptable if the team argues resource-based authorization is enough for this product.
- The CI score is my own estimate; the rubric's split of the 10 marks is unknown.

**Possible false negatives:**
- Frontend code (`web/app/page.tsx`, 576 lines) was skimmed for error handling and fetch use, not reviewed line by line.
- Dependency vulnerabilities were not scanned (no `pip-audit`/`npm audit` run).
- Earlier branches' history that was later rewritten or deleted on GitHub cannot be seen locally.

**Confidence by section:** CI/CD & testing — high · Project readiness — high (local), low (cloud) · Version control — high (history), medium (PR process) · Config & env — high · README — high · Error handling & logging — high · Security — medium-high (backend high, frontend medium) · Bonus — high · Exam readiness — medium (subjective).
