# Architecture & Routing

## 1. Routing Model: Local Dev & Ephemeral PR Subdomains
The project employs a dual-routing architecture tailored for local development and private ephemeral preview environments:

- **Local Development (`docker-compose.yml`)**:
  - Web UI: `http://localhost/` (root)
  - NextAuth: `http://localhost/api/auth`
  - API & Docs: `http://localhost/api` (Swagger docs at `/api/docs`)
  - Keycloak: `http://localhost/keycloak`
- **Ephemeral PR Preview Environments (`docker-compose.preview.yml`)**:
  - Each PR preview joins Tailscale as a lightweight ephemeral node: `https://pr-<PR_NUMBER>.<tailnet>.ts.net`
  - **Automatic Let's Encrypt TLS**: Tailscale Serve terminates HTTPS on port 443 with a valid certificate.
  - **WebAuthn Enabled**: Because the preview runs under trusted HTTPS, browsers treat it as a Secure Context (`window.isSecureContext === true`), allowing WebAuthn passkeys to work without security errors.
  - **Subdomain-Isolated Routing**:
    - Web UI: `https://pr-<PR_NUMBER>.<tailnet>.ts.net/` (root application, no `basePath`)
    - NextAuth: `https://pr-<PR_NUMBER>.<tailnet>.ts.net/api/auth`
    - API & Docs: `https://pr-<PR_NUMBER>.<tailnet>.ts.net/api`
    - Keycloak: `https://pr-<PR_NUMBER>.<tailnet>.ts.net/keycloak`

---

## 2. Traefik Routing Mechanics

### Ingress & Router Priorities
Traefik evaluates rules by descending `priority`:

| Service | Route Rule | Priority | Middleware | Forward Port |
| :--- | :--- | :---: | :--- | :--- |
| **Keycloak** | `PathPrefix(/keycloak)` | `200` | None (`KC_HTTP_RELATIVE_PATH=/keycloak`) | `8080` |
| **NextAuth** | `PathPrefix(/api/auth)` | `150` | None (routes auth requests to Next.js) | `3000` |
| **API (FastAPI)** | `PathPrefix(/api)` | `100` | `stripprefix` (strips `/api`) | `8000` |
| **Web (Next.js)** | `HostRegexp(...)` or `PathPrefix(/)` | `10` | None | `3000` |

### Key FastAPI Detail: `root_path`
Because Traefik strips the path prefix before forwarding requests to FastAPI (`uvicorn`):
- FastAPI must be informed of its subpath so that OpenAPI JSON and Swagger UI generate correct asset and fetch URLs.
- In `api/app/main.py`:
  ```python
  root_path = os.getenv("API_ROOT_PATH", "")
  app = FastAPI(title="SecretShare API", root_path=root_path)
  ```
- Configured in Compose:
  - Local: `API_ROOT_PATH=/api`
  - Preview: `API_ROOT_PATH=/pr-${PR_NUMBER}/api`

---

## 3. Nginx vs. Traefik & The Future Next.js Migration

### Why is Nginx used if Traefik is already a reverse proxy?
- **Traefik** is a reverse proxy / edge router. **It cannot serve static files from disk.**
- The `web` container runs `nginx:alpine` exclusively as a lightweight static file server, mounting `./web` to `/usr/share/nginx/html`.
- Traefik routes web requests to Nginx, and Nginx serves `index.html` and `app.js` with proper MIME types, caching headers (`ETag`, `Last-Modified`), and HTTP byte ranges.

### Migration to Next.js (Important Constraint)
- The user specifically requested to keep the current frontend minimal and simple because **the frontend will soon be migrated to Next.js**.
- When migrating to Next.js:
  1. Create the Next.js application in `./web`.
  2. In `docker-compose.yml` and `docker-compose.preview.yml`, replace the `nginx:alpine` image with the Next.js container (e.g. Node 20/22 running `npm run start` on port 3000).
  3. Point Traefik's `web` service to port `3000`.
  4. Nginx will be completely eliminated with zero backend changes.
