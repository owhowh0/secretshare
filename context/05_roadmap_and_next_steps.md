# Roadmap, Constraints & Known Issues

## 1. Constraints (don't break these)

- **Keep the frontend lean:** Next.js with plain CSS. No heavy component libraries or animation packages.
- **Preview routing is by subdomain** (`https://pr-<N>.<tailnet>.ts.net`). Don't reintroduce `/pr-N` path prefixes: WebAuthn and Web Crypto need a secure context and a per-preview origin.
- **Security invariants** (full table in `06_secret_lifecycle_and_e2e_encryption.md` §4):
  - The server stays blind to secret contents; it judges size only.
  - Single delivery, via the atomic recipient-checked burn.
  - Unknown, burned and expired ids are indistinguishable.
  - Nothing secret is logged, and payload ids never appear in URLs (AUD-6).
  - 422 responses never echo input.
- **Configuration goes through `Settings`**, never `os.getenv` in app code.
- **Tests stay green** in `test-api.yml`, `test-tls.yml` and the preview smoke battery. Security tests must not be skipped in CI.

See `07_working_conventions.md` for how changes are verified and merged.

---

## 2. Completed

| PR | Change |
| :--- | :--- |
| #18 | Tailscale HTTPS preview subdomains, Keycloak HTTPS issuer fixes, Swagger CSP |
| #19 | Centralized `pydantic-settings` configuration |
| #20 | Configurable TTL (5 min–24 h), byte-based 64 KB limit, domain exceptions, 422 without input echo |
| #21 | Alembic migrations on container start (audit log was silently empty before) |
| #22 | **E2E hybrid encryption:** per-device RSA-OAEP keys (IndexedDB), AES-256-GCM envelopes addressed to a recipient, auth-gated reveal, `/exists` pre-check, device key registry |
| #23 | Internal TLS for Postgres and Redis (`tls-init`, internal CA), `test-tls.yml` |
| #24, #25 | `docker-compose.preview.yml` doubles as a turnkey example stack; staging deploy made manual; git-divergence fix |
| #26 | **Denied reveal no longer burns the secret** (Lua burn); 21 stale tests fixed; preview smoke tests actually run now |
| #27 | `exists` moved from `GET /secrets/{id}/exists` to `POST /secrets/exists` (AUD-6) |
| #28 | Context folder brought up to date |
| #29 | Rate limits and audit use the real client IP behind Traefik and Tailscale (`TrustedProxyMiddleware`, `TRUSTED_PROXIES`) |

Note: the earlier plan of keeping the AES key in the URL `#fragment` was **not** built. #22 chose recipient-addressed envelopes with per-device RSA keys instead.

---

## 3. Known Issues / Next Candidates

Ordered roughly by impact.

1. **Staging is down.** Manual deploys fail: there's no `.env` on the server and `docker-compose.yml`'s Traefik conflicts with the shared one (troubleshooting §13).
2. **Decrypt-after-burn loss.** A recipient opening a secret on a device that isn't among `encrypted_keys` burns it and can't decrypt it. The client should send its `device_id`, and the server should refuse without burning when there's no match.
3. **Device private keys are `extractable: true`.** Prefer non-extractable `CryptoKey` objects in IndexedDB.
4. **`GET /api/keys/{user_id}` is unauthenticated** and allows username enumeration (404 vs 200). Consider requiring auth and returning a uniform response.
5. **Redis TLS hostname isn't checked** (`ssl_check_hostname=False`); only the certificate chain is verified.
6. **Only one test user in the realm.** Add a second user (e.g. `testuser2`) so the smoke tests can do a full "B denied → A succeeds" run end to end rather than via a non-existent recipient.

---

## 4. Feature Ideas (not started)

- **Sender dashboard:** list a user's active secrets (by creator `sub`), burn early, and view audit metadata (no plaintext). This needs a creator field on envelopes and audit rows (`actor_user_id` exists but isn't populated yet).
- **WebAuthn / passkey registration in the UI**, using Keycloak's WebAuthn support (previews already run in a secure context).
- **Slack / Teams platforms:** the `users.platform` and `device_keys.platform` columns already allow `slack`, `teams`, `keycloak` and `web`.
- **Production deployment** on a custom domain with ACME certificates.
