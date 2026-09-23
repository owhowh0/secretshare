# Data model — PostgreSQL

PostgreSQL holds identity, public keys, and the audit trail. It never holds
ciphertext and never holds private key material. Ciphertext lives only in Redis
under `s:{payload_id}` with a TTL, and private keys never leave the browser.

Migrations are managed with Alembic (`api/app/db/migrations`). The connection URL
carries the database password, so it is injected from `DATABASE_URL` at runtime and
is deliberately left empty in `alembic.ini`.

## Tables

### `users`

Identity of a person, created on the first device key registration.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` pk | |
| `platform` | `text` | `'slack'`, `'teams'`, `'keycloak'` or `'web'`, enforced by CHECK; the web client registers with `'web'` |
| `platform_user_id` | `text` | Keycloak `preferred_username` (or `sub` when absent); unique together with `platform` |
| `workspace_id` | `text` null | multi-tenant ready, single workspace in September |
| `created_at` | `timestamptz` | `now()` |

### `device_keys`

One row per enrolled browser. **Public keys only.**

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` pk | |
| `user_id` | `uuid` fk → `users` | `ON DELETE CASCADE` |
| `platform` | `text` | same values and CHECK as `users.platform`; default `'web'` |
| `public_key` | `text` | SPKI PEM, RSA-OAEP 2048 (see `crypto-spec.md`) |
| `label` | `text` null | e.g. `'Chrome on Windows'` |
| `created_at` | `timestamptz` | `now()` |
| `revoked_at` | `timestamptz` null | null means active |

`POST /keys/register` writes this table for the identity in the caller's access
token. In the same transaction it sets `revoked_at` on the user's active keys of
the same platform, so each user has at most one active key per platform.
`GET /keys/{user_id}` returns the active keys; it is unauthenticated (R-06 in
`api/docs/security/risk-register.md`).

### `audit_events`

Append-only record of security-relevant events.

| Column | Type | Notes |
|---|---|---|
| `id` | `bigserial` pk | |
| `event_type` | `text` | `created` \| `revealed` \| `expired` \| `denied`, enforced by CHECK |
| `payload_id_prefix` | `varchar(8)` null | first 8 characters only |
| `actor_user_id` | `uuid` null fk → `users` | `ON DELETE SET NULL` so identity deletion keeps the trail |
| `ip` | `inet` null | request source |
| `user_agent` | `text` null | truncated to 256 characters |
| `created_at` | `timestamptz` | `now()` |

Indexed on `created_at` and `payload_id_prefix` for incident-response queries.

## Why `payload_id_prefix` is 8 characters

A payload id is `secrets.token_urlsafe(32)` — 256 bits, 43 characters. Storing it
whole would put a working secret URL into a long-lived table, which contradicts
invariant 6 and would make the audit trail itself a target.

Eight base64url characters carry 48 bits. That is enough to correlate the
`created`, `revealed`, and `denied` events of one secret during an investigation,
and far too little to reconstruct the remaining 208 bits of the id.

Truncation happens in `AuditService.record`, and the column is `varchar(8)` with a
CHECK constraint, so a caller that passes a full id causes the write to fail rather
than silently persisting a usable id.

## Append-only enforcement

A `BEFORE UPDATE OR DELETE` trigger raises an exception on `audit_events`. A plain
`REVOKE` is not sufficient, because the API currently connects as the table owner
and an owner cannot revoke its own implicit rights.

**Known gap:** a superuser can still disable or drop the trigger. Closing it
requires running the API as a dedicated non-owner, non-superuser role. See AUD-3 in
`api/docs/security/security-controls.md` and R-09 in
`api/docs/security/risk-register.md`.

## Database roles

The API, Keycloak and the `keycloak-db-init` job connect with the same PostgreSQL
superuser (`POSTGRES_USER`). The Keycloak database runs on the same server. A
compromise of the API credentials therefore also exposes Keycloak's accounts and
credential hashes. Separate least-privilege roles are planned (R-09).

## Retention

`ip` and `user_agent` are personal data under GDPR. No automated retention job
exists yet; rows accumulate indefinitely. A retention policy and a deletion job are
required before any real-user deployment and are tracked as a limitation, not a
completed control (AUD-5, R-19).

## Backup

No backup job exists for either database (R-18). Redis is excluded from backups by
design: it holds only envelopes with a TTL and runs without persistence.
