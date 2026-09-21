# Architecture & Routing

## 1. Routing Model: Local Dev & Ephemeral PR Subdomains

The project employs a dual-routing architecture tailored for local development and private ephemeral preview environments:

### Local Development (`docker-compose.yml`)
- **Traefik Ingress**: Listens on `http://localhost:${TRAEFIK_WEB_PORT:-80}`.
- **Web UI (Next.js)**: `http://localhost/` (served from container on port 3000).
- **NextAuth**: `http://localhost/api/auth` (intercepted with priority 150 and routed to Next.js).
- **API & Swagger Docs**: `http://localhost/api` (Swagger UI at `http://localhost/api/docs`).
- **Keycloak**: `http://localhost/keycloak` (`KC_HTTP_RELATIVE_PATH=/keycloak`).
- **Datastores**: PostgreSQL (port 5432) for Keycloak and audit logging, Redis (port 6379) for ephemeral secrets and rate limiting.

### Ephemeral PR Preview Environments (`docker-compose.preview.yml`)
- **Tailscale Ephemeral Node**: Each preview environment joins the Tailscale tailnet as an ephemeral node: `https://pr-<PR_NUMBER>.<tailnet>.ts.net` (e.g. `https://pr-18.tail070378.ts.net`).
- **Automatic Let's Encrypt TLS**: Tailscale Serve terminates HTTPS on port 443 with a valid certificate generated automatically for the node's MagicDNS subdomain.
- **WebAuthn Passkey Support**: Because the environment is served under trusted HTTPS, modern browsers treat it as a **Secure Context** (`window.isSecureContext === true`). This allows WebAuthn passkey registration and authentication to work without origin or security errors.
- **Subdomain Routing & Traefik Ingress**:
  - Tailscale Serve forwards both port 443 (HTTPS) and port 80 (HTTP) internally to Traefik on `http://traefik:80`.
  - Traefik applies middleware to inject reverse-proxy headers: `X-Forwarded-Proto=https` and `X-Forwarded-Port=443`.
  - Routing rules match the PR hostname:
    - **Web Application**: `https://pr-<PR_NUMBER>.<tailnet>.ts.net/`
    - **NextAuth**: `https://pr-<PR_NUMBER>.<tailnet>.ts.net/api/auth`
    - **API & Docs**: `https://pr-<PR_NUMBER>.<tailnet>.ts.net/api` (Swagger docs at `/api/docs`)
    - **Keycloak Admin**: `https://pr-<PR_NUMBER>.<tailnet>.ts.net/keycloak`

---

## 2. Traefik Routing Mechanics

### Ingress & Router Priorities
Traefik evaluates rules by descending `priority`:

| Service | Route Rule | Priority | Middleware | Target Port |
| :--- | :--- | :---: | :--- | :---: |
| **Keycloak** | `PathPrefix(/keycloak)` | `200` | `proto-header` (`X-Forwarded-Proto=https`, `Port=443`) | `8080` |
| **NextAuth** | `PathPrefix(/api/auth)` | `150` | `proto-header` (routes auth to Next.js) | `3000` |
| **API (FastAPI)** | `PathPrefix(/api)` | `100` | `proto-header`, `stripprefix` (strips `/api`) | `8000` |
| **Web (Next.js)** | `Host(...)` / `PathPrefix(/)` | `10` | `proto-header` | `3000` |

In `docker-compose.preview.yml`, all routers also match `Host("${PR_HOSTNAME}") || Host("pr-${PR_NUMBER}.staging-server")` to isolate preview traffic by domain.

### FastAPI Dynamic `root_path` via Pydantic Settings
Because Traefik strips `/api` before passing the request to the Uvicorn worker:
- FastAPI must know its external mount path (`root_path`) so that generated OpenAPI JSON, Swagger UI bundles, and `/docs` assets resolve to `/api/docs`, `/api/openapi.json`, etc.
- In `api/app/core/config.py`, configuration is centralized in Pydantic `Settings`:
  ```python
  @property
  def root_path(self) -> str:
      if self.api_root_path is not None:
          return self.api_root_path
      if self.pr_number is not None:
          return f"/pr-{self.pr_number}/api"
      return "/api"
  ```
- In `api/app/main.py`:
  ```python
  settings = get_settings()
  app = FastAPI(
      title="SecretShare API",
      version="0.1.0",
      root_path=settings.root_path,
      lifespan=lifespan,
  )
  ```
- In Compose environments, `API_ROOT_PATH=/api` is passed, ensuring `settings.root_path` evaluates to `"/api"` consistently.

---

## 3. Frontend Architecture: Next.js 15 App Router

### Decommissioning of Nginx
- In earlier MVP prototypes, `nginx:alpine` was used as a temporary static file server for vanilla HTML/JS.
- **Nginx has been completely decommissioned and removed.**
- The frontend is now a modern **Next.js 15 App Router** application (`web/`) built with React 19 and TypeScript:
  - Containerized via multi-stage Node build in `web/Dockerfile`.
  - Runs with `next start -p 3000` in production.
  - Implements authentication via **NextAuth v5 (Auth.js)** (`web/auth.ts`).
  - Supports client-side secret creation, custom TTL selection, and payload retrieval via `/api/secrets`.
