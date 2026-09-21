# Secret Lifecycle & End-to-End Encryption

How a secret travels from sender to recipient, what the server stores, and the invariants that govern it. Read this before touching `api/app/services/secrets.py`, `api/app/storage/redis_store.py`, `api/app/api/routes/`, or `web/lib/`.

---

## 1. Model: Addressed, Hybrid-Encrypted Envelopes (PR #22)

A secret is **addressed to one recipient** (a Keycloak username) and **encrypted in the sender's browser** for every device that recipient has registered. The server never sees plaintext or an unwrapped key.

| Piece | Where it lives | Notes |
| :--- | :--- | :--- |
| Device RSA key pair (RSA-OAEP 2048, SHA-256) | Browser IndexedDB (`secretshare_keystore`, scoped per username) | Generated on first login by `web/lib/key-store.ts`. The private key never leaves the browser. |
| Device public key (SPKI PEM) | Postgres `device_keys` (linked to `users`) | Registered via `POST /api/keys/register`. |
| Per-secret AES-256-GCM key | Never stored raw | Wrapped with RSA-OAEP once per recipient device → `encrypted_keys[]`. |
| Envelope `{recipient_id, encrypted_keys[], iv, ciphertext}` | Redis `s:<payload_id>` as JSON, with TTL | Deleted atomically on the recipient's reveal. |
| Audit events | Postgres `audit_events` | Only an 8-character payload id prefix, never ciphertext. |

### Create (sender, `web/app/page.tsx` → `handleCreate`)
1. `GET /api/keys/{recipient_id}` → the recipient's active device public keys (404 if the recipient has none).
2. `encryptAesGcm(plaintext)` → `ciphertext`, `iv`, raw AES key.
3. Wrap the AES key with each device's RSA public key.
4. `POST /api/secrets` with the envelope and optional `ttl_seconds` → `{payload_id, ttl_seconds, expires_at}`.

### Reveal (recipient, `handlePreRevealCheck` → `handleConfirmReveal`)
1. `POST /api/secrets/exists {"payload_id"}` → non-destructive check before the confirmation modal.
2. `POST /api/secrets/reveal {"payload_id"}` with a Bearer token → envelope (the secret is burned server-side in the same step).
3. Try each `encrypted_keys[i]` with the local private key; decrypt the AES-GCM ciphertext in memory.

---

## 2. API Reference (current)

| Method & Path | Auth | Body | Response | Notes |
| :--- | :---: | :--- | :--- | :--- |
| `POST /api/keys/register` | Bearer | `{public_key (SPKI PEM), platform, label?}` | `DeviceKeyItem` 201 | User is get-or-created from `preferred_username` (falls back to `sub`). |
| `GET /api/keys/{user_id}` | none | — | `{user_id, keys[]}` or 404 | Public keys only. Unauthenticated (see known issues). |
| `POST /api/secrets` | none required | `{recipient_id, encrypted_keys[≥1], iv, ciphertext, ttl_seconds?}` | 201 `{payload_id, ttl_seconds, expires_at}` | Create rate limit. `ciphertext` ≤ `MAX_PAYLOAD_BYTES` **UTF-8 bytes**. TTL within `SECRET_TTL_MIN/MAX_SECONDS`. |
| `POST /api/secrets/exists` | none | `{payload_id}` | `{exists: bool}` | Non-destructive. Retrieve rate limit. (Was `GET /secrets/{id}/exists` until PR #27.) |
| `POST /api/secrets/reveal` | **Bearer** | `{payload_id}` | 200 envelope / 403 / 404 | 403 = caller isn't `recipient_id`, and the secret is **kept**. 404 = unknown, burned or expired (indistinguishable). |
| `GET /api/me` | Bearer | — | token claims | Wiring check. |
| `GET /api/health` | none | — | `{"status":"ok"}` | |

Error mapping lives in `api/app/api/errors.py`:
- `SecretNotFoundError` → 404 `"Secret not found or already retrieved"`
- `SecretAccessDeniedError` → 403
- `InvalidSecretTTLError` → 422
- `SecretStoreUnavailableError` → 503 + `Retry-After: 5`
- `RequestValidationError` → 422 with `input` stripped

There is deliberately **no `SecretExpiredError`** (see invariant 5).

---

## 3. The Atomic, Recipient-Checked Burn (PR #26)

`SecretStore.burn_for_recipient(payload_id, recipient_id)` runs one Lua script in Redis:

```lua
local payload = redis.call('GET', KEYS[1])
if not payload then return {'missing'} end
local ok, envelope = pcall(cjson.decode, payload)
if not ok or type(envelope) ~= 'table' or envelope['recipient_id'] ~= ARGV[1] then
  return {'denied'}
end
redis.call('DEL', KEYS[1])
return {'burned', payload}
```

- **Why not `GETDEL` and then check?** That was the original bug: a wrong recipient got a 403, but the secret was already deleted, and the real recipient then saw "already retrieved".
- **Why not `GET` → check in Python → `DEL`?** Two concurrent reveals by the recipient could both read the envelope before either deletes it, which breaks single delivery (invariant 3).
- A payload that isn't a JSON object with a matching `recipient_id` is never deleted by this path.
- Test doubles mirror the script: `tests/fakes.py::InMemorySecretStore` and `tests/test_config.py::RecordingRedis.eval`. The real script is exercised against Redis in `tests/security/test_secrets_invariants.py::TestDeniedRevealIsNonDestructive`, including 10 intruders racing 10 recipient calls.

The caller identity is `claims["preferred_username"]`, falling back to `claims["sub"]`. It must equal the `recipient_id` the sender used.

---

## 4. Security Invariants

The code cites numbered invariants from `CLAUDE.md`. That file is **gitignored**, so this is the list reconstructed from how the code uses each number. Treat `CLAUDE.md`, where available, as canonical.

| # | Invariant | Enforced by |
| :---: | :--- | :--- |
| 1 | The server is blind to envelope contents; it judges only total size. | `schemas/secrets.py`, `core/limits.py` (`BodySizeLimitMiddleware`) |
| 3 | Single delivery: two concurrent readers never both receive a secret. | Lua burn in `storage/redis_store.py` |
| 4 | Payload ids come from `secrets.token_urlsafe(32)` (≥ 43 characters, 256 bits). | `core/ids.py` |
| 5 | Unknown, burned and expired ids are indistinguishable (same status, body and headers). | one 404 handler; no expired error; audit failures swallowed |
| 6 | Nothing secret is logged: no full payload id, ciphertext or token. | `core/logging_filters.py`, `core/audit.py` (8-character prefix + DB CHECK) |

Related rules:
- **AUD-6:** a payload id never appears in a URL path or query string, because request lines are written to uvicorn and Traefik logs and to browser history. `/reveal` and `/exists` take it in the body. `tests/security/test_access_log.py::test_no_route_takes_a_payload_id_in_the_path` fails if any `/secrets` route gains a path parameter.
- **Payload cap:** 64 KB (`MAX_PAYLOAD_BYTES=65536`), measured in UTF-8 bytes.
- **No echoing:** 422 bodies never contain the rejected input.

---

## 5. Known Risks in This Area (not yet fixed)

- **Decrypt-after-burn loss:** the server burns on a successful `/reveal` before the browser tries to decrypt. If the recipient opens the link on a browser whose device key isn't in `encrypted_keys` (new browser, cleared IndexedDB), decryption fails and the secret is already gone. Possible fix: the client sends its `device_id`, and the server refuses (without burning) when no `encrypted_keys` entry matches it.
- **Device private key is generated `extractable: true`** in `web/lib/crypto.ts::generateRsaKeyPair`. Consider non-extractable keys stored as `CryptoKey` objects in IndexedDB.
- **`GET /api/keys/{user_id}` is unauthenticated,** and its 404 reveals whether a username has registered devices (user enumeration).
- **403 vs 404 on reveal** tells any holder of a payload id that the secret exists but belongs to someone else. This is accepted, since `/exists` reveals existence anyway.
