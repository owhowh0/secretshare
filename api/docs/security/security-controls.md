# Security controls

Each row states the security problem, why it matters for SecretShare specifically,
how it is implemented, how it was tested, and what it does **not** cover.

---

## Audit logging

### AUD-1 — Security events are not reconstructable after an incident

| | |
|---|---|
| **Security problem** | Without a durable record of who did what and when, an operator cannot answer whether a secret was read, by whom, or how often a link was probed. Incident response degrades to guesswork, and abuse is invisible. |
| **Relevance** | SecretShare's core promise is that a secret is read exactly once. If a sender asks "did anyone else open this?", the audit trail is the only thing that can answer, because the ciphertext itself is destroyed on read. |
| **Implementation** | `audit_events` table in PostgreSQL. `app/core/audit.py::AuditService.record` writes one row per event. `POST /secrets` records `created`; `POST /secrets/reveal` records `revealed` on a hit and `denied` on a miss. Rows carry event type, an 8-character payload id prefix, actor, IP, user agent, and a server timestamp. |
| **How tested** | `tests/security/test_audit.py::TestEventsRecorded` — asserts the correct event type for create, first read, second read, and unknown id. `tests/security/test_audit_db.py::TestAuditPersistence` — asserts the row actually lands in PostgreSQL with the expected fields. |
| **Limitations** | Only secret create and reveal are instrumented. `expired` is never emitted: Redis TTL expiry is silent, so detecting it needs keyspace notifications or a sweeper, neither of which exists. `actor_user_id` is always NULL until Step 3 binds requests to enrolled users. |

### AUD-2 — An audit trail must not itself leak the secret

| | |
|---|---|
| **Security problem** | A naive audit log stores the full resource identifier. For a burn-after-read relay the identifier *is* the capability: anyone who can read the log can read the URL. The audit table then becomes a more attractive target than the secret store, because it is long-lived while Redis is not. |
| **Relevance** | Invariant 6 — nothing secret is ever logged. A payload id grants access to a secret, so a stored full id would defeat burn-after-read for anyone with database or backup access. |
| **Implementation** | Only the first 8 characters are stored. Truncation is done inside `AuditService.record` via `payload_id_prefix()`, so no caller can opt out. Defence in depth: the column is `varchar(8)` with a `CHECK (length <= 8)`, so a full id fails the write instead of being stored. 8 base64url chars = 48 bits, versus the 256-bit id — enough to correlate events, not enough to reconstruct. Ciphertext is never passed to the audit layer at all. |
| **How tested** | `tests/security/test_audit.py::TestNoSecretMaterialInAudit` — asserts the full id never appears in a recorded event, that ciphertext never appears, and that 2000 generated prefixes stay collision-free. `tests/security/test_audit_db.py::TestDatabaseLevelGuards::test_full_payload_id_is_rejected_by_the_database` — raw SQL insert of a full id is rejected by PostgreSQL. |
| **Limitations** | The prefix is still a correlation handle: an attacker with database access learns how many secrets were sent, when, from which IP, and whether each was read. This is metadata leakage, which "zero-knowledge" was never claimed to cover. |

### AUD-3 — A compromised application must not be able to erase its own trail

| | |
|---|---|
| **Security problem** | An audit log that the application can rewrite proves nothing. An attacker who reaches code execution simply deletes the rows describing the intrusion. |
| **Relevance** | The relay is internet-facing and serves the JavaScript that performs encryption, so it is the most likely component to be compromised. Its audit trail must survive its own compromise to have evidential value. |
| **Implementation** | A `BEFORE UPDATE OR DELETE ... FOR EACH ROW` trigger on `audit_events` raises an exception, so tampering fails loudly. A `REVOKE` was tried first and rejected as ineffective: the API connects as the table owner, and an owner cannot revoke its own implicit rights — the `UPDATE` still succeeded in manual testing. |
| **How tested** | `tests/security/test_audit_db.py::TestDatabaseLevelGuards` — `UPDATE` and `DELETE` both raise, and the original row is verified unchanged and still present afterwards. Also confirmed manually via `psql`. |
| **Limitations** | **The control is incomplete.** The API connects as a superuser that owns the table, so it can `ALTER TABLE ... DISABLE TRIGGER` or drop the trigger and then tamper freely. Closing this requires a dedicated non-owner, non-superuser database role for the API, plus shipping rows off-host to append-only storage for real tamper-evidence. Neither is done. As it stands this raises the effort of tampering; it does not prevent it. |

### AUD-4 — Audit logging must not weaken the burn-after-read guarantee

| | |
|---|---|
| **Security problem** | Adding a database write to a request path creates two new failure modes: the endpoint can start failing when the database is down, and a miss can take measurably longer than a hit. Either turns the audit feature into an enumeration oracle. |
| **Relevance** | Invariant 5 — a missing secret and a burned secret must be indistinguishable. If a `denied` write behaved differently from a `revealed` write, an attacker could distinguish "never existed" from "already read", which reveals that a real secret was sent. |
| **Implementation** | `AuditService.record` catches every exception, logs it, and returns normally, so a PostgreSQL outage cannot change status code, body, or headers. Both the hit and miss paths perform exactly one audit write of the same shape before the response is built. When `DATABASE_URL` is unset the service disables itself rather than raising at request time. |
| **How tested** | `tests/security/test_audit.py::TestAuditDoesNotWeakenResponses` — a deliberately broken session factory still yields 201/200/404 with unchanged bodies, the failure is logged, and no ciphertext reaches the log. `test_burned_and_missing_responses_are_identical` compares status, JSON, and raw bytes of a burned id against an unknown id. |
| **Limitations** | Tested for equality of response content, not for timing. No statistical timing analysis has been run, and a slow database could in principle make one path measurably slower. Chosen trade-off is availability over audit completeness: if PostgreSQL is down, secrets still flow and events are lost, so the trail has gaps precisely during an outage. |

### AUD-5 — Audit records contain personal data

| | |
|---|---|
| **Security problem** | IP address and user agent are personal data under GDPR. Collecting them indefinitely without a retention policy is a compliance problem and increases the damage of a database breach. |
| **Relevance** | The project is a university deliverable that claims a privacy-preserving design; silently accumulating PII would contradict that claim. |
| **Implementation** | Collection is deliberate and limited: `ip` and `user_agent` only, user agent truncated to 256 characters to bound storage and stop header-stuffing. No request bodies, no headers beyond user agent, no ciphertext. |
| **How tested** | `tests/security/test_audit.py::test_request_metadata_is_captured` asserts the fields are populated. `test_long_user_agent_is_truncated` asserts the 256-character cap holds in PostgreSQL. |
| **Limitations** | **No retention or deletion job exists.** Rows accumulate forever. A retention period, an automated purge, and a documented lawful basis are all required before any real-user deployment. `ON DELETE SET NULL` on `actor_user_id` means deleting a user preserves their events in pseudonymous form, which is a deliberate choice that needs review if a right-to-erasure request ever applies. |

### AUD-6 — The full payload id was written to the web server access log

**Status: fixed. Found while testing AUD-2, closed on `fix/aud-6-payload-id-in-access-log`.**

| | |
|---|---|
| **Security problem** | The audit table stores only an 8-character prefix, but the payload id used to travel in the URL path of `GET /secrets/{id}`. Uvicorn's access log records the full request line, so the complete 43-character id — a working capability to read the secret — landed in plaintext logs, as did any copy held by a reverse proxy or the recipient's browser history. |
| **Relevance** | Directly contradicts invariant 6, and it defeated AUD-2: truncating the id in the database achieves little while the same id sits in the log next to it. Anyone with log access, including shipped or backed-up logs, could read secrets that had not yet been burned. |
| **Evidence (before)** | Observed during end-to-end testing: `INFO: 127.0.0.1 - "GET /secrets/<43-character id> HTTP/1.1" 200 OK`. Confirmed the id in the log matched the live secret, while `audit_events` correctly held only the 8-character prefix. |
| **Implementation** | Two layers. **Primary:** the id moved out of the URL. `GET /secrets/{payload_id}` is removed and replaced by `POST /secrets/reveal`, which takes `{"payload_id": "..."}` in the request body (`app/schemas/secrets.py::SecretRevealRequest`). A request body is not part of the request line, so no access log, proxy log, or browser history entry can contain it. `web/app/page.tsx` was updated to match. **Defence in depth:** `app/core/logging_filters.py::RedactSecretPaths` is attached to `uvicorn.access`, `uvicorn.error`, and `secretshare.api`, rewriting any `/secrets/<id>` path segment to `/secrets/<redacted>` before a handler formats the record. It scrubs both `record.msg` and `record.args`, because uvicorn passes the path as a format argument. This covers an old bookmarked link that still reaches the API, a future route that puts an id in a path, and the global exception handler, which logs `request.url.path`. |
| **How tested** | `tests/security/test_access_log.py` — `TestIdNeverReachesTheRequestLine` asserts the revealed id is absent from the request URL and that the id-bearing GET route no longer resolves while `POST /secrets/reveal` still returns the secret. `TestAccessLogRedaction` emits a uvicorn-shaped access record containing a real `new_payload_id()` and asserts the full id is absent from the captured log while `/secrets/<redacted>` is present; it also covers the exception-handler message, leaves `/health` and `/secrets/reveal` untouched, and asserts installation is idempotent. Verified against a live uvicorn as well — captured log and commands in `docs/security/evidence/aud-6-access-log.md`. |
| **Limitations** | The redaction filter only reaches Python's logging module inside this process. Logs written by Traefik, or by any proxy in front of the API, are not touched by it — they are protected only because the id is no longer in the URL, so a misconfigured future route could still leak through them. The filter's pattern is path-shaped: an id logged in some other position, for example inside a serialised request body, would not be matched. Nothing redacts ids from logs already written before this change; those must be rotated or destroyed. TLS terminates at the proxy, so the id is in a plaintext body on the proxy-to-API hop unless that hop is also encrypted. |

---

## Authentication

### AUTH-1 — Token validation errors disclosed why the token was rejected

| | |
|---|---|
| **Security problem** | `get_current_user` interpolated the PyJWT exception into the 401 body, returning `Token signing key not found: Unable to find a signing key that matches: 'unknown-kid'` or `Invalid token: Signature has expired`. Each failure mode produced a different message, so the endpoint answered "which part of your token is wrong?" for anyone who asked. That turns a single 401 into a forgery oracle: an attacker crafting a token learns whether the signature verified but the audience was wrong, whether the key id was unknown, or whether only the expiry failed, and fixes one field at a time. |
| **Relevance** | Brief §2 requires error handling that does not expose sensitive information, and CLAUDE.md §8 requires generic error responses with no variation between failure causes. The same reasoning already applied to secrets under invariant 5 — a missing and a burned secret are indistinguishable — was not applied to authentication, leaving the inconsistency on the one endpoint that guards every other one. |
| **Implementation** | `app/core/auth.py` returns a single module-level constant `_INVALID_TOKEN_DETAIL = "Invalid or expired token"` from both 401 paths, so the two branches are textually identical and cannot drift apart. The diagnostic detail is not discarded: each handler logs it to `secretshare.auth` at WARNING before raising, recording the exception type and message but never the token itself, since a bearer token is a live credential (invariant 6). The previously silent `except Exception` now logs via `logger.exception`, so an unexpected 503 is no longer undebuggable. `WWW-Authenticate: Bearer` is unchanged across all rejections. |
| **How tested** | `tests/security/test_auth_error_disclosure.py` — six distinct failure modes (expired, wrong audience, unknown kid, malformed, empty segments, tampered signature) are asserted to produce **byte-identical** response bodies, not merely equal status codes. A parametrised test asserts no PyJWT vocabulary (`signing key`, `kid`, `audience`, `signature`, `algorithm`, `PyJWK`, `Unable to find`) appears anywhere in any response. Two tests assert the reason *is* present in the server log via `caplog`, so the fix suppresses disclosure without destroying operator diagnostics, and one asserts the bearer token — and separately its signature segment — never reaches the log at any level. 13 tests, all passing. |
| **Limitations** | **Timing is not addressed and remains a potential oracle.** Measured over 30 requests per case against the test client, an expired token and an unknown `kid` were indistinguishable (median 2.11 ms vs 2.05 ms) — but only because the test JWKS is pre-cached in memory. In production an unrecognised `kid` can miss `PyJWKClient`'s cache and trigger a network fetch from Keycloak, which would make that path far slower than a locally-detected expiry and reintroduce the distinction the constant body removes. This has not been measured against a live Keycloak, so the control is verified for response *content* only. Closing it requires constant-time handling of the whole validation path and was explicitly out of scope here. The 503 for an unreachable Keycloak is also still distinguishable from a 401, which tells a prober about infrastructure state rather than about their token. Log volume is a second-order concern: a token-guessing attack now writes one WARNING per attempt, which is useful for detection but unbounded, and rate limiting rather than this control is what should bound it. |

---

## Notes on scope

Controls for atomic burn, TTL purge, ciphertext-only relay, CSPRNG payload IDs,
timing-safe 404, and Redis persistence disabled are required by CLAUDE.md §11.9 and
are **not yet written up here**. They belong to the Step 1 and Step 5 work and
should be added as rows in this same format.
