# AI Agent Context & Knowledge Base

Welcome! This folder contains complete technical context, architecture decisions, solved edge cases, and future roadmaps for the **SecretShare** project. If you are an AI assistant picking up this repository, read these documents before making changes.

---

## Index of Context Documents

1. [`01_architecture_and_routing.md`](01_architecture_and_routing.md)
   - Transition from fragile subdomains to robust path-based routing (`/`, `/api`, `/keycloak`).
   - Traefik reverse proxy configuration, priority rules, and prefix stripping.
   - Role of Nginx vs. Traefik, and preparation for future **Next.js** migration.

2. [`02_authentication_and_keycloak.md`](02_authentication_and_keycloak.md)
   - OIDC Authorization Code Flow with PKCE (S256).
   - Backend PyJWT + PyJWKClient token verification against Keycloak JWKS.
   - Test user credentials, realm configuration, and client settings.

3. [`03_troubleshooting_and_edge_cases.md`](03_troubleshooting_and_edge_cases.md)
   - **Crucial debugging log**: Detailed root causes and solutions for subtle edge cases encountered:
     - Subpath relative URL resolution (RFC 3986) on `/pr-<N>` causing 404s.
     - Web Cryptography API (`crypto.subtle`) unavailability in non-secure HTTP contexts.
     - Traefik multiple-router service binding requirements.
     - Docker Compose variable interpolation (`$$`) rules.
     - PostgreSQL volume initialization on persistent staging volumes.

4. [`04_ci_cd_and_deployment.md`](04_ci_cd_and_deployment.md)
   - GitHub Actions workflows: `test-api.yml` and `deploy-preview.yml`.
   - Tailscale SSH ephemeral preview deployment mechanics.
   - Comprehensive 9-step automated smoke test battery.

5. [`05_roadmap_and_next_steps.md`](05_roadmap_and_next_steps.md)
   - User preferences and behavioral constraints (e.g., minimal styling, lightweight JS).
   - Migration roadmap to Next.js.
   - Next steps for SecretShare feature development.

---

## Current Project Status
- **Active Branch**: `feat/oauth`
- **Active Pull Request**: PR #9 on `owhowh0/secretshare`
- **Current State**: Fully functional, path-based routing verified, OAuth PKCE login working, live smoke tests passing in CI/CD.
