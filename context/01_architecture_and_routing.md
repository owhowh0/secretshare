# Architecture & Routing

## 1. Components

| Service | Tech | Role |
| :--- | :--- | :--- |
| `web` | Next.js 15 App Router, React 19, NextAuth v5, port 3000 | UI, OIDC login, **client-side encryption/decryption** (`web/lib/crypto.ts`, `web/lib/key-store.ts`) |
| `api` | FastAPI (Python 3.12), uvicorn, port 8000 | Device keys, secret envelopes, audit. Runs Alembic migrations on start (`python -m app.db.migrate && exec uvicorn ...`). |
| `redis` | Redis 7, **TLS only** (`--tls-port 6379 --port 0`) | Ephemeral envelopes `s:<payload_id>` with TTL, rate-limit counters `rl:<scope>:<ip>` |
| `db` | PostgreSQL 16, **TLS** | App DB (`users`, `device_keys`, `audit_events`) and the Keycloak DB |
| `keycloak` | Keycloak 26, served under `/keycloak` | OIDC provider, realm `secretshare`, public client `secretshare-api` |
| `keycloak-db-init` | postgres image | Idempotently creates the Keycloak database |
| `tls-init` | alpine + openssl | Runs `tls/generate.sh` once into the `tls-certs` volume: an internal CA plus `db` and `redis` server certificates |
| `traefik` | Traefik | Edge router (its own service in `docker-compose.yml`; a shared global container on the staging server for previews) |
| `tailscale` | Tailscale sidecar (preview only) | Joins the tailnet as `pr-<N>`, terminates HTTPS with a Let's Encrypt certificate via Tailscale Serve |

The Nginx placeholder from the MVP is gone; Next.js serves its own assets.

### Internal TLS (PR #23)
- The `api` service gets `TLS_CA_CERT=/certs/ca.crt` (setting `tls_ca_cert`). Redis connects with `ssl_ca_certs` and `ssl_cert_reqs="required"`. Postgres uses an SSL context built from the same CA, including inside Alembic migrations.
- Redis hostname checking is currently off (`ssl_check_hostname=False` in `api/app/main.py`), so the certificate chain is verified but the hostname isn't.
- Covered by `api/tests/test_tls.py`, which runs in its own `test-tls.yml` workflow.

---

## 2. Compose Files & Environments

| File | Used for | Ingress |
| :--- | :--- | :--- |
| `docker-compose.yml` | Local dev and the (manual) staging deploy. Needs `.env` (`cp .env.example .env`). | Its own `traefik` on `${TRAEFIK_WEB_PORT:-80}` and dashboard `:8080`. `http://localhost/...` |
| `docker-compose.preview.yml` | Per-PR previews on `staging-server`, **and** a turnkey example stack with built-in defaults (`PR_NUMBER` defaults to `1`). | Attaches to the external `traefik-net` and the shared global `traefik`; the `tailscale` sidecar serves `https://pr-<N>.<tailnet>.ts.net` |

Both files declare `traefik-net` as `external: true`, so run `docker network create traefik-net` first.

---

## 3. Routing Model

### Local (`docker-compose.yml`), path-based on `localhost`
| Path | Target | Priority |
| :--- | :--- | :---: |
| `/keycloak` | Keycloak :8080 (`KC_HTTP_RELATIVE_PATH=/keycloak`) | 200 |
| `/api/auth` | Next.js :3000 (NextAuth) | 150 |
| `/api` | FastAPI :8000 (the `/api` prefix is stripped) | 100 |
| `/` | Next.js :3000 | 10 |

### Preview (`docker-compose.preview.yml`), host-based per PR
- URL: `https://pr-<N>.tail070378.ts.net` (the tailnet domain comes from CI).
- Every router matches `Host(`${PR_HOSTNAME:-pr-<N>.staging-server}`) || Host(`pr-<N>.staging-server`)` combined with the same path prefixes and priorities as above.
- Tailscale Serve proxies both :443 (HTTPS) and :80 to `http://traefik:80`. A Traefik `proto-header` middleware forces `X-Forwarded-Proto=https` and `X-Forwarded-Port=443`, so Keycloak issues `https://...` issuers without `:80` (troubleshooting §1).
- **Subdomains, not `/pr-N` paths:** WebAuthn and Web Crypto need a secure context and a stable origin per preview. Don't go back to path prefixes.

### FastAPI `root_path`
Traefik strips `/api`, so FastAPI must know its external prefix in order to generate correct Swagger and OpenAPI URLs. `Settings.root_path` (in `api/app/core/config.py`) resolves in this order:
1. `API_ROOT_PATH` if set.
2. `/pr-<PR_NUMBER>/api` if `PR_NUMBER` is set.
3. `/api` otherwise.

Both compose files set `API_ROOT_PATH=/api`.

---

## 4. Configuration

All runtime configuration goes through `app.core.config.Settings` (pydantic-settings; env vars or `.env`, case-insensitive). **Don't call `os.getenv` in app code.** Key fields:

| Setting | Default | Notes |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | `production` fails fast without `DATABASE_URL` / `KEYCLOAK_*` |
| `SECRET_TTL_SECONDS` / `_MIN_` / `_MAX_` | 600 / 300 / 86400 | Validated `min ≤ default ≤ max` |
| `MAX_PAYLOAD_BYTES` | 65536 | UTF-8 bytes; the body middleware allows +1 KB of JSON overhead |
| `CREATE_RATE_LIMIT` / `RETRIEVE_RATE_LIMIT` / `RATE_LIMIT_WINDOW_SECONDS` | 10 / 30 / 60 | Keyed by the real client IP (`rl:<scope>:<ip>` in Redis), resolved by `TrustedProxyMiddleware`. |
| `TRUSTED_PROXIES` | `127.0.0.1/32,::1/128` | Proxies whose `X-Forwarded-For`/`-Proto` are believed. Both compose files set the private ranges `10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`. See §5. |
| `TLS_CA_CERT` | unset | Enables TLS verification for Redis and Postgres |
| `AUDIT_ENABLED` | true | |

The request schemas read the TTL and size bounds **at import time** (so they appear in OpenAPI). The service layer re-checks TTL bounds against the live settings.

---

## 5. Client IP Resolution Behind Proxies (PR #29)

The API's TCP peer is always Traefik, and in previews Traefik's peer is the tailscale sidecar. The real client address is carried in `X-Forwarded-For`:

```
browser (100.x tailnet) → tailscale serve (sets XFF=100.x) → Traefik (appends sidecar 172.18.x) → API
```

- **API:** `app.core.proxy.TrustedProxyMiddleware` (outermost middleware). If the TCP peer is in `TRUSTED_PROXIES`, it walks `X-Forwarded-For` right to left and takes the first hop that isn't a trusted proxy. Client-written entries further left are ignored, so forging the header can't reset a rate-limit bucket. A malformed chain leaves the peer unchanged. `X-Forwarded-Proto` is applied the same way.
- **uvicorn** runs with `--no-proxy-headers`. Its own handling trusts only `127.0.0.1` and would never match Traefik.
- **Preview Traefik** (the global container started by `deploy-preview.yml`) runs with `--entrypoints.web.forwardedHeaders.trustedIPs=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`, so it keeps the sidecar's `X-Forwarded-For` instead of overwriting it with the sidecar's IP. The deploy recreates an older router that lacks the flag.
- Before this fix every caller mapped to Traefik's IP: one shared bucket of 10 creates per minute per stack, and a useless IP in audit rows.
- Tested in `api/tests/test_proxy.py` (spoofing, per-client buckets, audit IP, deployment wiring).
