# Authentication & Keycloak Implementation

## 1. Flow Overview
SecretShare uses standard **OpenID Connect (OIDC) / OAuth 2.0 Authorization Code Flow with PKCE (RFC 7636)**.

### PKCE Parameters:
- `code_verifier`: 64-character cryptographically secure random string (`[A-Za-z0-9-._~]`).
- `code_challenge_method`: `S256`
- `code_challenge`: `BASE64URL-ENCODE(SHA256(code_verifier))`

---

## 2. Keycloak Configuration

The Keycloak realm is automatically imported from [`keycloak/realm-export.json`](../keycloak/realm-export.json):

- **Realm**: `secretshare`
- **Client ID**: `secretshare-api`
- **Client Type**: Public client (`publicClient: true`, `clientAuthenticatorType: client-secret`)
- **Flows Enabled**:
  - `standardFlowEnabled: true` (Authorization Code Flow)
  - `directAccessGrantsEnabled: true` (Resource Owner Password Credentials grant, used exclusively for automated integration tests)
  - `implicitFlowEnabled: false` (disabled for security)
- **Allowed Redirect URIs**:
  ```json
  "redirectUris": [
    "http://localhost/*",
    "http://127.0.0.1/*",
    "http://localhost:*/*",
    "http://127.0.0.1:*/*",
    "http://staging-server/*"
  ]
  ```
- **Audience Mapper**: An OIDC audience protocol mapper (`secretshare-api-audience`) ensures the issued access tokens contain `"aud": "secretshare-api"`.

### Test Account:
- **Username**: `testuser`
- **Password**: `testpassword123`
- **Email**: `test@example.com`
- **Email Verified**: `true`

---

## 3. Backend Verification: PyJWT & PyJWKClient

### Why PyJWT instead of `python-jose`?
`python-jose` is unmaintained and does not have native support for dynamic JWKS key rotation or modern PyJWK clients.
The project migrated to **PyJWT** (`pyjwt>=2.8.0` with cryptography):

In `api/app/core/auth.py`:
- `jwt.PyJWKClient` connects to Keycloak's JWKS endpoint:
  `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/certs`
- Tokens are verified for:
  1. Signature (using the signing key retrieved dynamically via token header `kid`).
  2. Algorithm (`RS256`).
  3. Audience (`secretshare-api`).
  4. Expiration (`exp`).
  5. Issuer URL (`iss`).

### Protected Endpoints:
- `GET /api/me`: Returns the decoded token claims (`sub`, `preferred_username`, `email`).
- `POST /api/secrets` & `POST /api/secrets/reveal`: Accept optional `Authorization: Bearer <token>` to associate secrets with authenticated users. Reveal takes the payload id in the request body, not the path, so it never reaches an access log (AUD-6).
