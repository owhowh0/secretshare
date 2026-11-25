# Team Split — TODO.md

Balanced by effort points (S = 1, M = 2), not task count. Total 29 points.
Each member owns one area end to end: the change, its tests, and the README/evidence line for it.

| Member | Area | Tasks | Points | Status |
|---|---|---|---|---|
| 1 | CI/CD pipeline | T1, T4, T5, T6, T7 | 6 | ✅ **done — modified by Ionuț** (branch `feat/ci-cd-pipeline`) |
| 2 | Tests & health | T2, T3, T17 | 5 | ⏳ open |
| 3 | Security & auth | T12, T13, T14, T15 | 6 | ⏳ open |
| 4 | Config, environment & resilience | T8, T9, T10, T11 | 6 | ✅ **done — modified by Ecaterina** (2026-11-14, branch `chore/config-env-resilience`, not yet merged) |
| 5 | Logging & documentation | T16, T18, T19, T20 | 6 | ⏳ open |

**Progress:** 12 / 29 points done (9 / 20 tasks). Details of every change are in the T1, T4–T11 status blocks in `TODO.md`.

Member 2 has 5 points because T2 + T3 are the riskiest (new toolchain in CI); they also review Member 1's workflow PRs.

---

## Member 1 — CI/CD pipeline (6 pts) — ✅ DONE, modified by Ionuț
- ✅ **T1** test reports + coverage artifacts (S) · ✅ **T4** ruff lint step (S) · ✅ **T5** branch protection on `main` (S) · ✅ **T6** fix staging deploy + smoke step (M) · ✅ **T7** gitleaks + pip-audit/bun audit (S)
- **Status:** all five **modified by Ionuț** on branch `feat/ci-cd-pipeline`.
  - **T1**: Added `pytest-cov==6.0.0` to `api/requirements-dev.txt`; pytest steps in `.github/workflows/test-api.yml` and `test-tls.yml` write `--junitxml` and `--cov=app --cov-report=xml --cov-report=term`; artifacts uploaded via `actions/upload-artifact@v4` (`if: always()`); added `.github/scripts/report_summary.py` to publish pass/fail/coverage markdown tables to `$GITHUB_STEP_SUMMARY`.
  - **T4**: Added `ruff==0.8.4` to `api/requirements-dev.txt`; added `ruff check app tests` step to CI; cleaned all 15 unused imports (`F401`) across `api/app/schemas/__init__.py`, `api/tests/test_api.py`, `api/tests/test_keys.py`, `api/tests/test_secrets.py`, `api/tests/conftest.py`, and `api/tests/security/test_secrets_invariants.py`.
  - **T5**: Documented branch protection policy on `main` in `README.md` and created `docs/security/evidence/branch-protection-rules.md` (blocks direct pushes, enforces PRs, requires status checks for API tests, OAuth live tests, TLS tests, Gitleaks, pip-audit, and web audit).
  - **T6**: Hardened `.github/workflows/deploy-staging.yml` by auto-generating `.env` via `scripts/init-env.sh`, redirecting heredoc stdin (`</dev/null`), and adding post-deploy smoke checks (`wait_services_ready.sh`, `curl /api/health`, `test_web_routing.sh`) on standard port 80.
  - **T7**: Created `.github/workflows/security.yml` running Gitleaks secret scanning on full history (`fetch-depth: 0`), Python dependency auditing via `pip-audit`, and frontend dependency auditing via `bun audit`. Created `.gitleaks.toml` and `docs/security/evidence/security-audit-evidence.md`.
- **Exam questions:** What triggers each workflow and why? How do you prove the pipeline fails on a failing test (show run `35603690360`)? Why did red builds reach `main` before, and what stops it now? Unit vs integration vs E2E in your pipeline? Why service containers in one job and full `docker compose` in another? What does gitleaks catch that `.gitignore` doesn't?

## Member 2 — Tests & health (5 pts)
- **T2** web CI job: type-check, build, CSP tests (M) · **T3** crypto unit tests for `web/lib/crypto.ts` (M) · **T17** `/health/ready` readiness endpoint + tests (S)
- **Depends on:** Member 1 for report/artifact format (T1) so web results look the same. Member 4's T11 timeouts are done (**modified by Ecaterina**): reuse `create_redis_client()` and the `*_TIMEOUT_SECONDS` settings for `/health/ready`; `api/tests/test_timeouts.py` shows the hung-dependency test pattern.
- **Exam questions:** How do you test encryption without a browser? Why test that a *wrong* key and *tampered* ciphertext fail? What is the CSP positive control proving? Liveness vs readiness — why keep both? What isn't tested yet and why?

## Member 3 — Security & auth (6 pts)
- **T12** verify JWT `iss` (S) · **T13** harden Keycloak realm (M) · **T14** close Traefik dashboard (S) · **T15** auth on `GET /keys/{user_id}` + roles decision (M)
- **Depends on:** Prod-mode Keycloak (T10) is done (**modified by Ecaterina**). The `keycloak_issuer` setting was **not** part of T8–T11, so add it yourself in T12 (`api/app/core/config.py` + compose) — no longer blocked. Member 1 must update `deploy-preview.yml:155,166-169` alongside T13 (it rewrites redirect URIs).
- **Exam questions:** Walk through the auth flow (PKCE → token → JWKS check). Why check `iss` and `aud`? Why does a denied reveal not burn the secret (Lua script)? Why one generic 401/404 message? Why no RBAC — what does resource-based authorization give you here? Present one security improvement end to end: AUD-6 (risk, fix, before/after log evidence, regression test).

## Member 4 — Config, environment & resilience (6 pts) — ✅ DONE, modified by Ecaterina
- ✅ **T8** fix `.env.example` Redis URL + README prod path (S) · ✅ **T9** remove fallback secrets from compose, add `scripts/init-env.sh` (S) · ✅ **T10** dev/prod separation, `ENVIRONMENT=production`, Keycloak `start`, `docker-compose.dev.yml` (M) · ✅ **T11** explicit timeouts + api resource limits, `api/tests/test_timeouts.py` (M)
- **Status:** all four **modified by Ecaterina** on 2026-11-14, branch `chore/config-env-resilience` (not yet merged). Verified locally: API suite 187 passed, prod-mode stack + CI smoke/OAuth/CSP tests green. Files and evidence per task: `TODO.md` T8–T11.
- **Remaining handoffs:** Member 1 re-runs CI/preview after the push; staging server's `.env` needs `AUTH_SECRET`; `keycloak_issuer` setting moved to Member 3 (T12).
- **Exam questions:** How are secrets handled from `.env` to container to app (pydantic-settings)? Why fail fast in production but degrade in development? What breaks if `REDIS_URL` is `redis://` (show the bug you fixed)? Why is the rate limiter fail-open, and is that the right trade-off? What happens to a request when Redis hangs, and how long does it wait?

## Member 5 — Logging & documentation (6 pts)
- **T16** logging config, request IDs, `LOG_LEVEL`, redaction fix (M) · **T18** README: design decisions, trade-offs, known limitations, security improvements, test reports (M) · **T19** fill `api-contract.md` (S) · **T20** merge the pending `docs/security-documentation` commits (S)
- **Depends on:** everyone — write T18 last, after the other members' PRs land, so it describes the final state. Gather one paragraph per area from each member.
- **Exam questions:** What do you log, what do you never log, and how is that tested (`test_access_log.py`)? Why does the audit log store only an 8-char id prefix? Explain the architecture diagram and why a modular monolith. Name three known limitations and why they were accepted. How would you trace one request through Traefik → API → Redis?

---

## Order of work
1. **Week 1:** T20 (Member 5) · ~~T8, T9~~ ✅ (Member 4, modified by Ecaterina) · T1, T4, T7 (Member 1) · T3 (Member 2) · T12, T14 (Member 3; adds the issuer setting itself)
2. **Week 2:** T2, T17 · ~~T10, T11~~ ✅ (Member 4, modified by Ecaterina) · T13, T15 · T16 · T6
3. **Week 3:** T5 (once all jobs exist) · T18, T19 (final docs) · whole team rehearses the exam questions above
