# Roadmap & Guidelines for Future AI Assistants

## 1. User Constraints & Architectural Invariants (CRITICAL)

- **Minimal, Focused Frontend Design**:
  The Next.js frontend (`web/`) should remain lightweight, clean, and responsive. Avoid pulling in heavy component libraries, complex animation packages, or unnecessary dependencies.
- **Routing Architecture**:
  - Local development runs on `http://localhost/` via Traefik port 80.
  - Preview deployments run on `https://pr-<PR_NUMBER>.<tailnet>.ts.net` via Tailscale HTTPS with automatic TLS.
  - Do not introduce path-based prefixes (e.g. `/pr-N`) for preview environments; subdomain isolation is required for WebAuthn passkey origins.
- **Security Invariants (Non-Negotiable)**:
  - **AUD-6 Compliance**: Payload IDs must be passed in JSON request bodies (`POST /api/secrets/reveal`), never in URL paths or query parameters.
  - **No Input Echoing**: Validation exceptions (422) must never reflect client input or secret text back in the response body.
  - **Access Log Redaction**: Logging filters in `api/app/core/logging_filters.py` must remain installed at module import and in lifespan to prevent sensitive URI logging.
- **Maintain Test Integrity**:
  All changes must pass:
  - Fast unit and security tests: `uv run pytest -c api/pytest.ini api/tests/`
  - GitHub Actions pipelines: `.github/workflows/test-api.yml` and `.github/workflows/deploy-preview.yml`.

---

## 2. Completed Milestones

- [x] **Next.js 15 App Router Frontend**: Replaced static Nginx placeholder with Next.js 15, React 19, TypeScript, and NextAuth v5.
- [x] **Tailscale HTTPS Preview Subdomains**: Ephemeral preview containers with automatic Let's Encrypt TLS certificates.
- [x] **WebAuthn Passkey Support**: Enabled in preview environments via browser-recognized Secure Contexts (`https://*.ts.net`).
- [x] **Centralized Runtime Configuration**: `app.core.config.Settings` via `pydantic-settings` replacing all scattered `os.getenv` calls.
- [x] **Configurable Secret TTL & Payload Limits**: Configurable TTL (5 min – 24 hours), 64 KB payload size enforcement, and domain exceptions.
- [x] **Automatic Alembic Migrations**: Synchronous database schema migration runner on container startup.
- [x] **Swagger UI / ReDoc CSP Fix**: Dedicated CSP policy allowing CDN bundles on documentation routes.

---

## 3. Upcoming Feature Roadmap

### A. Client-Side End-to-End Encryption (Zero-Knowledge Architecture)
- Encrypt secret plaintext in the user's browser using Web Crypto API (`AES-GCM-256`) before transmission.
- The decryption key is encoded in the URL hash fragment (`#key=...`) upon creation.
- Because URL hash fragments are never sent to the server in HTTP requests:
  - The API receives and stores only AES ciphertext.
  - The server remains completely blind to the secret contents, achieving true zero-knowledge privacy.

### B. Authenticated User Dashboard
- For users authenticated via Keycloak:
  - Display active secrets created by the user (`sub`).
  - Provide an option to manually burn a secret before its TTL expires.
  - Display audit access metadata (burn timestamp, client IP, user agent) without exposing secret plaintext.

### C. WebAuthn Passkey Registration Flow in UI
- Leverage Keycloak's WebAuthn support to allow users to register biometric or hardware passkeys directly from the SecretShare frontend interface.

### D. Production Deployment with Custom Domain
- Final production deployment strategy for the `main` branch:
  - Configure production reverse proxy with a custom public domain (e.g. `secretshare.io`).
  - Automated certificate provisioning via Let's Encrypt (ACME).
