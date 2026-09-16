# Data model — PostgreSQL

PostgreSQL holds identity, public keys, and the audit trail. It never holds
ciphertext and never holds private key material. Ciphertext lives only in Redis
under `s:{payload_id}` with a TTL, and private keys never leave the browser.

Migrations are managed with Alembic (`api/app/db/migrations`). The connection URL
carries the database password, so it is injected from `DATABASE_URL` at runtime and
is deliberately left empty in `alembic.ini`.

## Tables

### `users`

Identity of a person on a chat platform.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` pk | |
| `platform` | `text` | `'slack'` or `'teams'`, enforced by CHECK |
| `platform_user_id` | `text` | unique together with `platform` |
| `workspace_id` | `text` null | multi-tenant ready, single workspace in September |
| `created_at` | `timestamptz` | `now()` |

### `device_keys`

One row per enrolled browser. **Public keys only.**

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` pk | |
| `user_id` | `uuid` fk → `users` | `ON DELETE CASCADE` |
| `public_key` | `text` | SPKI DER, base64 |
| `label` | `text` null | e.g. `'Chrome on Windows'` |
| `created_at` | `timestamptz` | `now()` |
| `revoked_at` | `timestamptz` null | null means active |

Table exists from the first migration because `audit_events.actor_user_id`
references `users`. The key-registration endpoints are Step 3 work and are not
implemented yet.

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
requires running the API as a dedicated non-owner, non-superuser role. See
`docs/security/security-controls.md`.

## Retention

`ip` and `user_agent` are personal data under GDPR. No automated retention job
exists yet; rows accumulate indefinitely. A retention policy and a deletion job are
required before any real-user deployment and are tracked as a limitation, not a
completed control.
