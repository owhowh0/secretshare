# Troubleshooting & Edge Cases Encountered

This document details critical edge cases encountered during development, along with their root causes and permanent fixes. Keep these in mind when touching routing, deployment, or authentication code.

---

## 1. Subpath Relative Resolution Edge Case (RFC 3986)

### Symptom:
Preview deployment reported success, but navigating to `http://staging-server/pr-9` showed an unresponsive page where clicking "Login with Keycloak" did nothing. Browser console showed `404 Not Found` for `http://staging-server/app.js`.

### Root Cause:
- When a user requests `http://staging-server/pr-9` without a trailing slash, the browser URL path is `/pr-9`.
- Under RFC 3986, `pr-9` is treated as a filename inside `/`.
- Any relative URL in the document like `<script src="app.js"></script>` resolves against `/`, resulting in `http://staging-server/app.js`!
- Traefik has no route for `/app.js`, returning `404 Not Found`.

### Solution:
1. **Traefik 308 Permanent Redirect**: In `docker-compose.preview.yml`, a redirect router catches `Path(/pr-${PR_NUMBER})` and redirects to `/pr-${PR_NUMBER}/`.
2. **Client-Side Normalization**: At the top of `<head>` in `web/index.html`:
   ```javascript
   if (window.location.pathname.match(/^\/pr-\d+$/)) {
     window.location.replace(window.location.pathname + '/' + window.location.search + window.location.hash);
   }
   ```
3. **Explicit Script Loading**: In `web/index.html`, load `app.js` using `${basePath}/app.js` instead of a naive relative URL.

---

## 2. Web Cryptography API Unavailable in Non-Secure Contexts

### Symptom:
When clicking the "Login with Keycloak" button on `http://staging-server/pr-9`, the browser alerted:
```
Failed to start login: Cannot read properties of undefined (reading 'digest')
```

### Root Cause:
- According to W3C Web Cryptography specs, `window.crypto.subtle` is **only exposed in secure contexts** (`HTTPS` or `localhost`).
- On `http://staging-server/pr-9` (accessed over Tailscale via plain HTTP), `window.crypto.subtle` is `undefined`.

### Solution:
Added an RFC 7636-compliant pure JavaScript SHA-256 fallback (`sha256Sync`) inside `web/app.js`:
```javascript
async function sha256Challenge(verifier) {
  let hashBytes;
  if (window.crypto && window.crypto.subtle && window.crypto.subtle.digest) {
    try {
      const data = new TextEncoder().encode(verifier);
      const hash = await window.crypto.subtle.digest('SHA-256', data);
      hashBytes = new Uint8Array(hash);
    } catch (e) {
      hashBytes = sha256Sync(verifier);
    }
  } else {
    hashBytes = sha256Sync(verifier);
  }
  // Base64URL encode hashBytes...
}
```

---

## 3. Traefik Router Dropped When Service is Missing

### Symptom:
Adding a redirect router in Docker Compose caused `/pr-9` to return `404 Not Found` from Nginx instead of redirecting.

### Root Cause:
- When a container defines multiple Traefik routers (e.g., `pr-9-web` and `pr-9-web-redirect`), Traefik requires **every** router to specify its target service explicitly.
- Without `service: pr-9-web`, Traefik logs `router has no service` and discards the redirect router completely.

### Solution:
Always define `traefik.http.routers.<name>.service=<service-name>` on all routers of a multi-router container:
```yaml
- "traefik.http.routers.pr-${PR_NUMBER}-web-redirect.service=pr-${PR_NUMBER}-web"
- "traefik.http.routers.pr-${PR_NUMBER}-web.service=pr-${PR_NUMBER}-web"
```

---

## 4. Docker Compose Variable Interpolation (`$$`)

### Symptom:
Writing Traefik regexes in `docker-compose.yml` like `regex=^.*(/pr-${PR_NUMBER})$` failed with invalid reference or bash syntax errors.

### Root Cause:
- In Docker Compose files, a single `$` is treated as variable interpolation.
- To pass a literal `$` to a container label (e.g. for regex end-of-line `$`), it **must be escaped as `$$`**.
- Similarly, regex group references must be `$${1}` or `$$1`.

### Solution:
```yaml
- "traefik.http.middlewares.pr-${PR_NUMBER}-redirect-slash.redirectregex.regex=^.*(/pr-${PR_NUMBER})$$"
- "traefik.http.middlewares.pr-${PR_NUMBER}-redirect-slash.redirectregex.replacement=$${1}/"
```

---

## 5. PostgreSQL Volume Init Scripts on Persistent Volumes

### Symptom:
On staging server, Compose mounts `./init-db:/docker-entrypoint-initdb.d:ro`. When adding Keycloak's database, the database was not created.

### Root Cause:
PostgreSQL only runs `/docker-entrypoint-initdb.d` scripts when the database volume is initialized for the first time. Existing staging volumes skipped the script, leaving the Keycloak database missing.

### Solution:
Added a dedicated lightweight `keycloak-db-init` container in `docker-compose.preview.yml` that runs `psql` to idempotently check and create the database if it doesn't already exist before Keycloak starts:
```yaml
SELECT format('CREATE DATABASE %I', '${KEYCLOAK_DB}')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${KEYCLOAK_DB}')\gexec
```

---

## 6. Testing Node.js Environment Lacking `sessionStorage`

### Symptom:
Running `pytest` in CI threw:
```
ReferenceError: sessionStorage is not defined
```

### Root Cause:
Standard Node.js (used to execute `node -e` during tests) does not have a global `sessionStorage` object like browsers do.

### Solution:
In `api/tests/test_frontend_and_routing.py`, mock `global.sessionStorage` in the test runner:
```javascript
global.sessionStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
```
