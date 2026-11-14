# Team Split — TODO.md

Balanced by effort points (S = 1, M = 2), not task count. Total 29 points.
Each member owns one area end to end: the change, its tests, and the README/evidence line for it.

| Member | Area | Tasks | Points |
|---|---|---|---|
| 1 | CI/CD pipeline | T1, T4, T5, T6, T7 | 6 |
| 2 | Tests & health | T2, T3, T17 | 5 |
| 3 | Security & auth | T12, T13, T14, T15 | 6 |
| 4 | Config, environment & resilience | T8, T9, T10, T11 | 6 |
| 5 | Logging & documentation | T16, T18, T19, T20 | 6 |

Member 2 has 5 points because T2 + T3 are the riskiest (new toolchain in CI); they also review Member 1's workflow PRs.

---

## Member 1 — CI/CD pipeline (6 pts)
- **T1** test reports + coverage artifacts (S) · **T4** ruff lint step (S) · **T5** branch protection on `main` (S) · **T6** fix staging deploy + smoke step (M) · **T7** gitleaks + pip-audit/bun audit (S)
- **Depends on:** Member 2's `test-web.yml` (T2) existing before T5 marks it required. Member 4's T9 (`:?` required vars) may break CI env generation in `test-api.yml:101-115` — re-run after it lands.
- **Exam questions:** What triggers each workflow and why? How do you prove the pipeline fails on a failing test (show run `35603690360`)? Why did red builds reach `main` before, and what stops it now? Unit vs integration vs E2E in your pipeline? Why service containers in one job and full `docker compose` in another? What does gitleaks catch that `.gitignore` doesn't?

## Member 2 — Tests & health (5 pts)
- **T2** web CI job: type-check, build, CSP tests (M) · **T3** crypto unit tests for `web/lib/crypto.ts` (M) · **T17** `/health/ready` readiness endpoint + tests (S)
- **Depends on:** Member 1 for report/artifact format (T1) so web results look the same. Member 4's T11 timeouts affect how fast `/health/ready` reports a dead dependency.
- **Exam questions:** How do you test encryption without a browser? Why test that a *wrong* key and *tampered* ciphertext fail? What is the CSP positive control proving? Liveness vs readiness — why keep both? What isn't tested yet and why?

## Member 3 — Security & auth (6 pts)
- **T12** verify JWT `iss` (S) · **T13** harden Keycloak realm (M) · **T14** close Traefik dashboard (S) · **T15** auth on `GET /keys/{user_id}` + roles decision (M)
- **Depends on:** Member 4 for the new `KEYCLOAK_ISSUER` setting and the prod-mode Keycloak (T10). Member 1 must update `deploy-preview.yml:155,166-169` alongside T13 (it rewrites redirect URIs).
- **Exam questions:** Walk through the auth flow (PKCE → token → JWKS check). Why check `iss` and `aud`? Why does a denied reveal not burn the secret (Lua script)? Why one generic 401/404 message? Why no RBAC — what does resource-based authorization give you here? Present one security improvement end to end: AUD-6 (risk, fix, before/after log evidence, regression test).

## Member 4 — Config, environment & resilience (6 pts)
- **T8** fix `.env.example` Redis URL + README prod path (S) · **T9** remove fallback secrets from compose (S) · **T10** dev/prod separation, `ENVIRONMENT=production`, Keycloak `start` (M) · **T11** explicit timeouts + api resource limits (M)
- **Depends on:** Member 1 to re-check CI/preview after T9/T10. Provides `keycloak_issuer` setting for Member 3 (T12) — do that first.
- **Exam questions:** How are secrets handled from `.env` to container to app (pydantic-settings)? Why fail fast in production but degrade in development? What breaks if `REDIS_URL` is `redis://` (show the bug you fixed)? Why is the rate limiter fail-open, and is that the right trade-off? What happens to a request when Redis hangs, and how long does it wait?

## Member 5 — Logging & documentation (6 pts)
- **T16** logging config, request IDs, `LOG_LEVEL`, redaction fix (M) · **T18** README: design decisions, trade-offs, known limitations, security improvements, test reports (M) · **T19** fill `api-contract.md` (S) · **T20** merge the pending `docs/security-documentation` commits (S)
- **Depends on:** everyone — write T18 last, after the other members' PRs land, so it describes the final state. Gather one paragraph per area from each member.
- **Exam questions:** What do you log, what do you never log, and how is that tested (`test_access_log.py`)? Why does the audit log store only an 8-char id prefix? Explain the architecture diagram and why a modular monolith. Name three known limitations and why they were accepted. How would you trace one request through Traefik → API → Redis?

---

## Order of work
1. **Week 1:** T20, T8, T9 (Members 5, 4) · T1, T4, T7 (Member 1) · T3 (Member 2) · T12, T14 (Member 3, after Member 4 adds the issuer setting)
2. **Week 2:** T2, T17 · T10, T11 · T13, T15 · T16 · T6
3. **Week 3:** T5 (once all jobs exist) · T18, T19 (final docs) · whole team rehearses the exam questions above
