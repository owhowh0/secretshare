# Authentication & Keycloak Implementation

## 1. Flow Overview
SecretShare uses standard **OpenID Connect (OIDC) / OAuth 2.0 Authorization Code Flow with PKCE (RFC 7636)**.

### PKCE Mechanics:
- `code_verifier`: 43–128 character cryptographically secure random string (`[A-Za-z0-9-._~]`).
- `code_challenge_method`: `S256`
- `code_challenge`: `BASE64URL-ENCODE(SHA256(code_verifier))`

---

## 2. Keycloak Configuration & Realm Import

The realm configuration is maintained in [`keycloak/realm-export.json`](../keycloak/realm-export.json):

- **Realm**: `secretshare`
- **Client ID**: `secretshare-api`
- **Client Type**: Public client (`publicClient: true`, `clientAuthenticatorType: client-secret`)
- **Flows Enabled**:
  - `standardFlowEnabled: true` (Authorization Code Flow with PKCE)
  - `directAccessGrantsEnabled: true` (Resource Owner Password Credentials grant, used exclusively in automated integration tests)
  - `implicitFlowEnabled: false` (disabled for security)
- **Allowed Redirect URIs**:
  ```json
  "redirectUris": [
    "http://localhost/*",
    "http://127.0.0.1/*",
    "http://localhost:*/*",
    "http://127.0.0.1:*/*",
    "http://staging-server/*",
    "https://*.ts.net/*"
  ]
  ```
- **Audience Mapper**: An OIDC protocol mapper (`secretshare-api-audience`) ensures access tokens contain `"aud": "secretshare-api"`.

### Dynamic Database Injection in Preview CI
When preview environments run on persistent staging volumes, Keycloak skips re-importing `realm-export.json`. To ensure newly spawned PR subdomains (`pr-${PR_NUMBER}.tail...ts.net`) are immediately recognized:
- In `.github/workflows/deploy-preview.yml`, a step executes SQL against Keycloak's Postgres database:
  ```sql
  INSERT INTO redirect_uris (client_id, value)
  SELECT id, 'https://${PR_HOSTNAME}/*'
  FROM client
  WHERE client_id='secretshare-api'
    AND NOT EXISTS (SELECT 1 FROM redirect_uris WHERE client_id=client.id AND value='https://${PR_HOSTNAME}/*');
  ```

### HTTPS Issuer & Port Normalization
When Keycloak runs behind Traefik and Tailscale HTTPS:
- Traefik injects `X-Forwarded-Proto=https` and `X-Forwarded-Port=443`.
- Keycloak container is configured with:
  - `KC_PROXY_HEADERS: "xforwarded"`
  - `KC_HOSTNAME_PORT: "443"`
  - `KC_HOSTNAME_URL: "https://${PR_HOSTNAME}/keycloak"`
  - `KC_HOSTNAME_ADMIN_URL: "https://${PR_HOSTNAME}/keycloak"`
- This guarantees the OIDC discovery document (`.well-known/openid-configuration`) publishes `issuer: "https://${PR_HOSTNAME}/keycloak/realms/secretshare"` without appending an erroneous `:80` port.

### Test User Account
- **Username**: `testuser`
- **Password**: `testpassword123`
- **Email**: `test@example.com`
- **Role**: Default realm user

---

## 3. Frontend Integration: NextAuth v5 (Auth.js)

The Next.js frontend (`web/`) integrates authentication via **NextAuth v5**:

- Configured in [`web/auth.ts`](../web/auth.ts) and exposed through App Router route handler at [`web/app/api/auth/[...nextauth]/route.ts`](../web/app/api/auth/[...nextauth]/route.ts).
- Uses `KeycloakProvider` with:
  - `clientId`: `secretshare-api`
  - `issuer`: `http://localhost/keycloak/realms/secretshare` (local) or `https://${PR_HOSTNAME}/keycloak/realms/secretshare` (preview).
  - `trustHost: true` enabled to allow reverse-proxy hostname resolution without hardcoding static URLs.
- **Session & JWT Callbacks**:
  - Intercepts Keycloak tokens on login and exposes `accessToken` and `username` inside the client session.
  - Client components access session state via `useSession()` from `next-auth/react`.

### WebAuthn Passkeys Support
Because preview deployments run under valid Let's Encrypt HTTPS via Tailscale (`https://*.ts.net`), the origin satisfies the browser's **Secure Context** (`window.isSecureContext === true`). Keycloak WebAuthn and passkey flows can be tested and used without browser security rejections.

---

## 4. Backend Verification: PyJWT & PyJWKClient

Located in [`api/app/core/auth.py`](../api/app/core/auth.py):

- **Key Retrieval**: `jwt.PyJWKClient` connects to Keycloak's JWKS endpoint:
  ```
  ${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/certs
  ```
- **Token Verification**:
  1. Signature (verified using the public RSA key indicated by token header `kid`).
  2. Algorithm (`RS256`).
  3. Audience (`secretshare-api`).
  4. Expiration (`exp`).
  5. Issuer URL (`iss`).
- **Failure responses:** every rejected token gets the same `401 "Invalid or expired token"` (the reason is logged server-side only). An unreachable JWKS endpoint gives 503. A missing `Authorization` header gives 403 (FastAPI `HTTPBearer`).

### Where auth is required
| Endpoint | Auth | Identity used |
| :--- | :--- | :--- |
| `GET /api/me` | Bearer | returns the claims |
| `POST /api/keys/register` | Bearer | device key owner = `preferred_username` (fallback `sub`) |
| `POST /api/secrets/reveal` | **Bearer (required)** | must equal the envelope's `recipient_id`, otherwise 403 and the secret is kept |
| `POST /api/secrets`, `POST /api/secrets/exists`, `GET /api/keys/{user_id}` | none | — |

**Identity contract:** the sender addresses a secret to a Keycloak **username** (`recipient_id`). The API compares it with the caller's `preferred_username` (or `sub` when that claim is missing). Renaming a user in Keycloak therefore orphans secrets and device keys addressed to the old name.

**AUD-6:** payload ids travel only in JSON bodies (`/reveal`, `/exists`), never in URLs. See `06_secret_lifecycle_and_e2e_encryption.md`.

### Test user
Only one user exists in the realm, `testuser` / `testpassword123`. The preview smoke test covers the wrong-recipient case by addressing a secret to a non-existent `someone-else-e2e` and revealing it as `testuser`.
