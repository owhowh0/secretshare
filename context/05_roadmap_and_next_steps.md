# Roadmap & Important Guidelines for Future AI Assistants

## 1. User Constraints & Preferences (CRITICAL)

- **Do NOT over-style the current vanilla frontend**:
  The user explicitly said: *"keep what was before, this is too much. also split the js and keep it as simple as possible cuz we'll use next js later"*.
  Avoid adding large CSS libraries, heavy glassmorphism, or framework bloat to `web/index.html` or `web/app.js`.
- **Maintain Path-Based Routing**:
  Do NOT revert to subdomains (`app.localhost` or `pr-9.staging-server`). All services must continue to use path prefixes (`/`, `/api`, `/keycloak`).
- **Keep Tests Passing**:
  Any changes to endpoints, tokens, or frontend structure must keep both `test-api.yml` and `deploy-preview.yml` smoke test batteries green.

---

## 2. Next Steps & Feature Roadmap

### A. Next.js Frontend Migration
The current HTML + vanilla JS frontend in `./web` is an ephemeral MVP placeholder.
- **Migration Plan**:
  1. Initialize Next.js in `./web` (e.g. Next.js App Router).
  2. Implement an OAuth client using NextAuth.js or pure OIDC PKCE client components.
  3. Create Dockerfile for the Next.js container (exposing port 3000).
  4. In `docker-compose.yml` and `docker-compose.preview.yml`, update `web` service to build from `./web` and route Traefik to port 3000.
  5. Remove Nginx entirely.

### B. Secret Expiration & TTL Customization
- Allow users to set a custom Time-To-Live (e.g. 5 minutes, 1 hour, 24 hours).
- Pass TTL parameter to Redis `SETEX`.

### C. Passphrase-Protected Encryption (Client-Side)
- Encrypt secret ciphertext in the browser using AES-GCM before sending to `/api/secrets`.
- Store only ciphertext on the server; the key or passphrase remains client-side.

### D. User Secret History (Authenticated Users)
- When authenticated with Keycloak, link secrets to user `sub`.
- Provide a dashboard showing active links and access logs (without storing plaintext).
