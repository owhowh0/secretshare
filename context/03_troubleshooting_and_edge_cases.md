# Troubleshooting & Edge Cases Encountered

This document details critical edge cases encountered during development, along with their root causes and permanent fixes. Consult this log whenever modifying routing, deployment, authentication, or container configurations.

---

## 1. Keycloak HTTPS Issuer Port 80 Leakage (`:80` in Discovery Document)

### Symptom:
After deploying preview environments with Tailscale HTTPS, navigating to `https://pr-18.tail...ts.net/api/auth/signin` produced a NextAuth configuration failure:
```
[auth][error] Configuration: Issuer URL mismatch
Status code: 500 Internal Server Error
```
Inspecting `https://pr-18.../keycloak/realms/secretshare/.well-known/openid-configuration` revealed:
`"issuer": "https://pr-18.tail070378.ts.net:80/keycloak/realms/secretshare"` (port 80 erroneously appended to HTTPS scheme).

### Root Cause:
Tailscale Serve was terminating HTTPS on port 443 and proxying traffic internally to Traefik on port 80. Traefik received requests on port 80 and forwarded `X-Forwarded-Port: 80` to Keycloak. Keycloak combined `X-Forwarded-Proto: https` with port `80`, generating invalid issuer URLs with `:80`.

### Solution:
1. In `docker-compose.preview.yml`, added Traefik custom headers middleware to explicitly enforce port 443:
   ```yaml
   traefik.http.middlewares.pr-${PR_NUMBER}-proto-header.headers.customrequestheaders.X-Forwarded-Proto=https
   traefik.http.middlewares.pr-${PR_NUMBER}-proto-header.headers.customrequestheaders.X-Forwarded-Port=443
   ```
2. Configured Keycloak container environment:
   ```yaml
   KC_PROXY_HEADERS: "xforwarded"
   KC_HOSTNAME_PORT: "443"
   KC_HOSTNAME_URL: "https://${PR_HOSTNAME}/keycloak"
   KC_HOSTNAME_ADMIN_URL: "https://${PR_HOSTNAME}/keycloak"
   ```

---

## 2. Keycloak Redirect URI Mismatches on Persistent Staging Volumes

### Symptom:
When opening the Keycloak login page on an ephemeral preview domain (`https://pr-<N>.tail...ts.net`), Keycloak displayed an error page:
```
Invalid parameter: redirect_uri
```

### Root Cause:
Although `keycloak/realm-export.json` was updated to include `"https://*.ts.net/*"`, Keycloak only imports `realm-export.json` when the database is created for the first time. On persistent staging servers where the Postgres volume already existed, Keycloak skipped realm import, keeping only the old redirect URIs.

### Solution:
In `.github/workflows/deploy-preview.yml`, added an idempotent post-startup step that executes SQL directly on the running Keycloak database:
```bash
docker compose -p "pr-${PR_NUM}" -f docker-compose.preview.yml exec -T db psql -U secretshare -d "keycloak_pr_${PR_NUM}" -c \
  "INSERT INTO redirect_uris (client_id, value) SELECT id, 'https://${PR_HOSTNAME}/*' FROM client WHERE client_id='secretshare-api' AND NOT EXISTS (SELECT 1 FROM redirect_uris WHERE client_id=client.id AND value='https://${PR_HOSTNAME}/*');"
```

---

## 3. Tailscale Dual Serve Ingress & Runner Local Resolution

### Symptom:
- Accessing the preview stack over HTTP (`http://pr-<N>...`) hung or timed out.
- Local CI verification scripts on the staging server failed to resolve `pr-<N>.tail...ts.net` via local DNS before MagicDNS propagation finished.

### Root Cause:
1. Tailscale Serve was initially only listening on port 443, dropping plain HTTP port 80 health probes.
2. The staging server's local resolver had not yet registered the new ephemeral Tailscale node hostname in its local `/etc/resolv.conf`.

### Solution:
1. Dual-port Tailscale Serve in `tailscale/serve.json` and CLI activation:
   ```bash
   tailscale serve --bg --https=443 / http://traefik:80
   tailscale serve --bg --http=80 http://traefik:80
   ```
2. In `deploy-preview.yml`, retrieve the ephemeral Tailscale node IP (`tailscale ip -4`) and inject it into `/etc/hosts` for the deployment job, cleaning it up on teardown:
   ```bash
   PR_IP=$(docker compose exec -T tailscale tailscale ip -4 | head -n1)
   echo "${PR_IP} ${PR_HOSTNAME}" >> /etc/hosts
   ```

---

## 4. FastAPI Swagger UI / ReDoc CSP Violations

### Symptom:
Accessing `https://pr-<N>.../api/docs` showed a blank page. The browser console reported multiple Content Security Policy (CSP) violations:
```
Refused to load script https://cdn.jsdelivr.net/... because it violates script-src 'self'
Refused to load image data:... because it violates img-src 'self'
```

### Root Cause:
`SecurityHeadersMiddleware` applied a strict default CSP (`script-src 'self'`) across all API responses. FastAPI's built-in Swagger UI and ReDoc templates load their JavaScript and CSS bundles from `cdn.jsdelivr.net` and load the Swagger favicon as a `data:` URI.

### Solution:
In [`api/app/core/headers.py`](../api/app/core/headers.py), dynamically relax the CSP header on documentation routes:
```python
is_docs_route = path in ("/docs", "/redoc", "/openapi.json") or path.endswith(("/docs", "/redoc", "/openapi.json"))
if is_docs_route:
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://cdn.jsdelivr.net;"
    )
```

---

## 5. Information Disclosure in HTTP 422 Validation Errors

### Symptom:
When a client submitted an oversized payload or invalid secret, FastAPI's default `RequestValidationError` handler returned the full invalid payload in the `input` field of the error response:
```json
{
  "detail": [
    {
      "loc": ["body", "ciphertext"],
      "msg": "string too long",
      "input": "<raw confidential secret text...>"
    }
  ]
}
```

### Root Cause:
FastAPI/Pydantic default exception handlers reflect user input in error details. For a secret-sharing application, echoing secret ciphertext violates confidentiality guarantees.

### Solution:
In [`api/app/api/errors.py`](../api/app/api/errors.py), registered custom exception handlers that strip all `input` fields from `RequestValidationError` responses, returning sanitized error locations and messages only.

---

## 6. Audit Log Silently Empty: Migrations Never Ran (PR #21)

### Symptom:
Everything looked healthy (smoke tests green), but `audit_events` was empty. API logs showed `relation "audit_events" does not exist` on every create and reveal (24 times in 10 minutes on one preview).

### Root Cause:
Nothing ran `alembic upgrade head` in preview or staging, and the API image didn't even contain `alembic.ini`. `AuditService` deliberately swallows write failures (a DB outage must not change secret responses, per invariant 5), so the failure was invisible.

### Solution:
- `api/app/db/migrate.py` (`python -m app.db.migrate`) upgrades to head. It's a no-op when already current and is skipped when `DATABASE_URL` is unset.
- The container `CMD` runs it before uvicorn (`... && exec uvicorn ...`). A failed migration stops the container.
- The `Dockerfile` copies `alembic.ini`.
- Tested in `api/tests/test_migrate.py`, including a real upgrade against `TEST_DATABASE_URL` in a subprocess. Running Alembic in-process would let `env.py`'s `fileConfig` reset pytest's loggers.

---

## 7. Centralized Configuration with Pydantic Settings

### Symptom:
Inconsistent configuration across modules: some files called `os.getenv("DATABASE_URL")`, others had fallback defaults in routes, leading to merge conflicts between preview routing and configuration branches.

### Root Cause:
Direct `os.getenv` calls were scattered throughout the codebase without unified validation or type coercion.

### Solution:
Implemented centralized [`api/app/core/config.Settings`](../api/app/core/config.py) using `pydantic-settings`. All runtime variables (Redis URL, DB URL, rate limits, secret TTL bounds, CORS origins, and dynamic `root_path`) are validated at startup. Direct `os.getenv` calls are forbidden outside of config initialization.

---

## 8. Historical Edge Cases Log

### A. Subpath Relative Resolution (RFC 3986)
- **Symptom**: Navigating to `/pr-9` without a trailing slash caused relative asset requests (`app.js`) to resolve against `/` instead of `/pr-9/`.
- **Solution**: Traefik redirect regex middleware normalizes URLs to include trailing slashes.

### B. Web Cryptography API Unavailable in Plain HTTP
- **Symptom**: `window.crypto.subtle` is `undefined` over plain HTTP, so PKCE and (now) all E2E encryption in `web/lib/crypto.ts` fail.
- **Solution**: Previews run only over trusted Tailscale HTTPS (a secure context), and PKCE is handled by NextAuth. The old hand-written JS SHA-256 fallback (`web/lib/pkce.ts`) was removed, and a test asserts it stays gone. Local `http://localhost` still counts as a secure context in browsers.

### C. Traefik Router Dropped When Service is Missing
- **Symptom**: Multi-router containers dropped secondary routers with `router has no service`.
- **Solution**: Always specify `traefik.http.routers.<name>.service=<service>` explicitly on every router.

### D. Docker Compose Variable Interpolation (`$$`)
- **Symptom**: Traefik regex patterns containing `$` failed to parse in Compose.
- **Solution**: Escape all literal dollar signs in compose files as `$$` (e.g. `$$1`, `^.*$$`).

### E. PostgreSQL Volume Initialization on Persistent Staging Volumes
- **Symptom**: Mounts to `/docker-entrypoint-initdb.d` were ignored if the data directory was already initialized.
- **Solution**: Dedicated `keycloak-db-init` container runs idempotent `CREATE DATABASE ... WHERE NOT EXISTS` via `psql`.

---

## 9. Preview Deploy Green, but the Smoke Tests Never Ran (fixed in PR #26)

### Symptom:
`Deploy Ephemeral Preview` passed, yet the log ended right after the Keycloak `psql` step. There was no output from `wait_services_ready.sh` or any E2E script. The smoke scripts were also outdated for the #22 API contract, and nobody noticed.

### Root Cause:
The remote script is sent as a heredoc on stdin (`tailscale ssh ... "bash -s" << 'EOF'`). `docker compose exec -T db psql ...` inherits that stdin and **reads the rest of the script as its own input**. Bash then hits EOF and exits 0.

### Solution:
- Every `docker compose ... exec -T` in the heredoc gets `</dev/null`.
- The SSH output is `tee`d to `deploy.log`, and the step fails unless `all verification tests passed successfully` appears in it.
- **Rule:** any command inside that heredoc that can read stdin (`exec`, `ssh`, `read`, `psql` without `-c`...) must have `</dev/null`.

---

## 10. Wrong Recipient Burned the Secret (fixed in PR #26)

### Symptom:
User B opens a secret meant for user A and gets 403 "not the intended recipient" (correct). When A opens it afterwards, A gets 404 "already retrieved".

### Root Cause:
`retrieve_secret` did `GETDEL` first and compared `recipient_id` afterwards, so the delete had already happened.

### Solution:
The recipient check and the delete now run together in one Redis Lua script (`SecretStore.burn_for_recipient`). See `06_secret_lifecycle_and_e2e_encryption.md` §3. The regression tests include a race between 10 intruders and 10 recipient calls on real Redis.

---

## 11. API Contract Changed, Tests Left Behind (fixed in PR #26)

### Symptom:
`main` was red: 21 failing tests, all `KeyError: 'payload_id'`, `422 != 201`, or `403 != 404/500`.

### Root Cause:
PR #22 made `recipient_id`, `encrypted_keys` and `iv` required and put `/reveal` behind auth, but older suites still posted `{"ciphertext": ...}` with no signed-in user.

### Solution:
Shared helpers `secret_body()` and `recipient_claims()` in `api/tests/fakes.py`. Every route test now uses them. When a contract changes, update tests, `.github/scripts/*.sh` and `web/` in the same PR.

---

## 12. Stacked PR Closed When Its Base Branch Was Deleted

### Symptom:
After merging #19 with `--delete-branch`, PR #20 (based on #19's branch) showed as **closed** and couldn't be retargeted ("Cannot change the base branch of a closed pull request").

### Solution:
Re-push the deleted base branch, reopen the PR, retarget it to `main`, then delete the branch again. Better: retarget child PRs **before** deleting the parent's branch.

---

## 13. Staging Deploy Keeps Failing (open)

As of 2026-09-21, `deploy-staging.yml` (manual `workflow_dispatch`) fails and the staging stack is broken: `staging-db-1` has exited, and `staging-api-1` and `staging-traefik-1` are stuck in `Created`. Known causes:
1. **No `/opt/secretshare/.env`** on the server, so `POSTGRES_PASSWORD` is empty and Postgres refuses to start. The staging workflow, unlike the preview workflow, doesn't generate secrets.
2. **Port conflict:** `docker-compose.yml` starts its own Traefik on :80/:8080, but the shared global `traefik` container (used by previews) already holds those ports on the same host.
3. (Fixed in #24) The server's `main` had a local commit that diverged from origin. The workflow now does `git fetch` + `checkout -B main origin/main` + `reset --hard`.

A likely fix: deploy staging through `docker-compose.preview.yml`-style routing on the shared Traefik (e.g. a `staging` hostname) and generate `.env` once on the server.

---

## 14. Rate Limits Shared by All Users Behind Traefik (fixed in PR #29)

### Symptom:
All users of a stack shared 10 creates per minute; repeated smoke runs hit 429. The audit `ip` column always held Traefik's container address.

### Root Cause:
- uvicorn ran with `--proxy-headers` but no `--forwarded-allow-ips`, so it trusted only `127.0.0.1` and used the TCP peer (Traefik, `172.18.0.3`) as the client.
- In previews, the global Traefik didn't trust forwarded headers from the tailscale sidecar, so it replaced the client IP with the sidecar's.

### Solution:
`TrustedProxyMiddleware` with `TRUSTED_PROXIES` on the API; `--no-proxy-headers` for uvicorn; `forwardedHeaders.trustedIPs` on the preview Traefik. See `01_architecture_and_routing.md` §5.

### Pitfall:
Never trust `*` or read the **leftmost** `X-Forwarded-For` entry: the client writes that one, and trusting it lets anyone pick a fresh address for every request.
