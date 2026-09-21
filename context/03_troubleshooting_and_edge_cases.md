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

## 6. Automatic Alembic Database Migrations on Startup

### Symptom:
When deploying preview or staging environments with clean databases, the API container crashed with `UndefinedTableError: relation "audit_events" does not exist`.

### Root Cause:
Alembic migrations were not executed automatically as part of container initialization.

### Solution:
Implemented [`api/app/db/migrate.py`](../api/app/db/migrate.py), invoked directly before the API application serves traffic in [`api/Dockerfile`](../api/Dockerfile) and in testing suites:
```python
def run_migrations():
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
```

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
- **Symptom**: Calling `window.crypto.subtle.digest('SHA-256')` over plain HTTP threw `Cannot read properties of undefined (reading 'digest')`.
- **Solution**: Ephemeral previews now run exclusively over trusted Tailscale HTTPS (Secure Context). A synchronous JS SHA-256 fallback remains in place for legacy offline environments.

### C. Traefik Router Dropped When Service is Missing
- **Symptom**: Multi-router containers dropped secondary routers with `router has no service`.
- **Solution**: Always specify `traefik.http.routers.<name>.service=<service>` explicitly on every router.

### D. Docker Compose Variable Interpolation (`$$`)
- **Symptom**: Traefik regex patterns containing `$` failed to parse in Compose.
- **Solution**: Escape all literal dollar signs in compose files as `$$` (e.g. `$$1`, `^.*$$`).

### E. PostgreSQL Volume Initialization on Persistent Staging Volumes
- **Symptom**: Mounts to `/docker-entrypoint-initdb.d` were ignored if the data directory was already initialized.
- **Solution**: Dedicated `keycloak-db-init` container runs idempotent `CREATE DATABASE ... WHERE NOT EXISTS` via `psql`.
