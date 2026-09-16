# Architecture & Path-Based Routing

## 1. Why Path-Based Routing (No Subdomains)?
Initially, the project explored subdomain-based routing (e.g. `app.localhost`, `pr-9.api.staging-server`).
**Problem**:
- Subdomains require wildcard DNS or `/etc/hosts` hacks on every developer machine and Tailscale node.
- On private networks (Tailscale), subdomains like `*.staging-server` do not resolve without MagicDNS or custom split-DNS configurations.
- Visiting preview environments failed because machines could not resolve the hostnames.

**Decision**:
Transition entirely to **pure path-based routing**:
- Local Development:
  - Web UI: `http://localhost/` (root)
  - API & Docs: `http://localhost/api` (Swagger docs at `/api/docs`)
  - Keycloak: `http://localhost/keycloak`
- Ephemeral PR Preview Environments:
  - Web UI: `http://staging-server/pr-<PR_NUMBER>/`
  - API & Docs: `http://staging-server/pr-<PR_NUMBER>/api` (Swagger docs at `/pr-<PR_NUMBER>/api/docs`)
  - Keycloak: `http://staging-server/pr-<PR_NUMBER>/keycloak`

---

## 2. Traefik Routing Mechanics

### Ingress & Router Priorities
Traefik evaluates rules by descending `priority`:

| Service | Route Rule | Priority | Middleware | Forward Port |
| :--- | :--- | :---: | :--- | :---: |
| **Keycloak** | `PathPrefix(/keycloak)` or `PathPrefix(/pr-<N>/keycloak)` | `200` | None (`KC_HTTP_RELATIVE_PATH` configured in Keycloak) | `8080` |
| **API (FastAPI)** | `PathPrefix(/api)` or `PathPrefix(/pr-<N>/api)` | `100` | `stripprefix` (strips `/api` or `/pr-<N>/api`) | `8000` |
| **Web Redirect** | `Path(/pr-<N>)` | `20` | `redirectregex` (redirects to `/pr-<N>/`) | `80` (Web) |
| **Web (Nginx)** | `PathPrefix(/)` or `PathPrefix(/pr-<N>)` | `10` | `stripprefix` (on preview: strips `/pr-<N>`) | `80` |

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
