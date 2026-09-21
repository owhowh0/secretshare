# AI Agent Context & Knowledge Base

Welcome! This directory contains the complete technical context, architectural decisions, solved edge cases, and future roadmaps for the **SecretShare** project. If you are an AI assistant picking up this repository, read these documents before making changes.

---

## Index of Context Documents

1. [`01_architecture_and_routing.md`](01_architecture_and_routing.md)
   - Dual routing architecture: Local development (`localhost`) vs. Ephemeral PR Preview Environments (`pr-<N>.<tailnet>.ts.net`).
   - Next.js App Router frontend on port 3000 (Nginx has been decommissioned).
   - Traefik reverse proxy configuration, priority rules, and prefix stripping.
   - FastAPI dynamic `root_path` via centralized Pydantic Settings.

2. [`02_authentication_and_keycloak.md`](02_authentication_and_keycloak.md)
   - OIDC Authorization Code Flow with PKCE (RFC 7636).
   - Keycloak realm configuration, wildcard/preview redirect URIs, and HTTPS issuer configuration.
   - NextAuth v5 (Auth.js) frontend integration with Keycloak provider and session management.
   - Backend PyJWT + PyJWKClient token verification against Keycloak JWKS.
   - Secure Context and WebAuthn passkey readiness over Tailscale HTTPS.

3. [`03_troubleshooting_and_edge_cases.md`](03_troubleshooting_and_edge_cases.md)
   - **Crucial debugging log**: Detailed root causes and solutions for subtle edge cases encountered:
     - Keycloak HTTPS issuer port 80 leakage in OIDC discovery.
     - Persistent Keycloak database redirect URI synchronization.
     - Tailscale Serve dual-port proxying and local runner `/etc/hosts` resolution.
     - FastAPI Swagger UI / ReDoc Content Security Policy (CSP) allowlisting.
     - NextAuth v5 reverse proxy URL handling.
     - Alembic migrations automation on container startup.
     - Pydantic Settings centralization and merge conflict resolution.
     - RFC 3986 relative URL resolution, Web Cryptography secure contexts, and Compose variable escaping (`$$`).

4. [`04_ci_cd_and_deployment.md`](04_ci_cd_and_deployment.md)
   - GitHub Actions workflows: `test-api.yml` (unit, config, migrate, security, integration) and `deploy-preview.yml`.
   - Ephemeral preview deployment with Tailscale container sidecar and Let's Encrypt TLS.
   - Automated preview verification battery: routing, Swagger docs, Keycloak auth exchange, and secret lifecycle.
   - Prominent preview URL reporting in GITHUB_STEP_SUMMARY, console banner, and sticky PR comments.

5. [`05_roadmap_and_next_steps.md`](05_roadmap_and_next_steps.md)
   - User preferences and behavioral constraints (clean Next.js design, maintain test suites).
   - Completed milestones: Next.js migration, HTTPS subdomain preview, Pydantic settings, configurable TTLs.
   - Upcoming features: Client-side AES-GCM encryption, authenticated secret dashboard, WebAuthn UI flows.

---

## Current Project Status
- **Active Branch**: `main`
- **Recent Merged PRs**:
  - PR #18 (`feat/infra-fix`): Ephemeral Tailscale HTTPS preview subdomains, WebAuthn enablement, Keycloak HTTPS issuer fixes, and Swagger CSP.
  - PR #19 (`feat/settings-config`): Centralized runtime configuration via `pydantic-settings`.
  - PR #20 (`feat/secret-ttl-exceptions`): Configurable secret TTL, payload byte limits, domain exceptions, sanitized 422 errors.
  - PR #21 (`fix/run-migrations-on-start`): Automatic Alembic migrations on API container start.
- **Current State**: Fully functional, Next.js 15 App Router web UI, NextAuth v5 OIDC login, FastAPI backend with Redis ephemeral storage & Postgres audit logging, live preview CI/CD with valid Let's Encrypt HTTPS certificates.
