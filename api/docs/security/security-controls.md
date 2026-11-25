# Security controls

Each row states the security problem, why it matters for SecretShare specifically,
how it is implemented, how it was tested, and what it does **not** cover.

Web application controls (WEB-x) are documented in `docs/security/security-controls.md`.
Requirement, threat and risk identifiers refer to `security-requirements.md`,
`threat-model.md` and `risk-register.md` in this directory.

| ID | Control | Requirement |
|---|---|---|
| AUD-1 | Security events recorded in an audit log | SR-25 |
| AUD-2 | Audit log holds no secret material | SR-23 |
| AUD-3 | Append-only audit table | SR-25 |
| AUD-4 | Audit failures do not change responses | SR-09 |
| AUD-5 | Limited personal data in audit records | SR-27 |
| AUD-6 | Payload id removed from the access log | SR-23 |
| AUTH-1 | Uniform token rejection message | SR-09 |
| AUTH-2 | Access token verification | SR-03, SR-08 |
| AUTH-3 | Reveal bound to the recipient's identity | SR-19 |
| SEC-1 | Atomic, recipient-checked burn | SR-19, SR-20 |
| SEC-2 | Bounded lifetime and non-persistent store | SR-22 |
| SEC-3 | Unguessable payload identifiers | SR-21 |
| SEC-4 | Uniform response for unknown, burned and expired secrets | SR-09 |
| API-1 | Request body size limit | SR-07 |
| API-2 | Schema validation without input echo | SR-07, SR-09 |
| API-3 | Rate limiting | SR-24 |
| API-4 | Client address resolution behind proxies | SR-24 |
| API-5 | API response security headers | SR-28 |
| TLS-1 | TLS between the API and the data stores | SR-02 |
| DB-1 | Parameterised data access | SR-13 |

---

## Audit logging

### AUD-1 — Security events are not reconstructable after an incident

| | |
|---|---|
| **Security problem** | Without a durable record of who did what and when, an operator cannot answer whether a secret was read, by whom, or how often a link was probed. Incident response degrades to guesswork, and abuse is invisible. |
| **Relevance** | SecretShare's core promise is that a secret is read exactly once. If a sender asks "did anyone else open this?", the audit trail is the only thing that can answer, because the ciphertext itself is destroyed on read. |
| **Implementation** | `audit_events` table in PostgreSQL. `app/core/audit.py::AuditService.record` writes one row per event. `POST /secrets` records `created`; `POST /secrets/reveal` records `revealed` on a hit and `denied` on a miss. Rows carry event type, an 8-character payload id prefix, actor, IP, user agent, and a server timestamp. |
| **How tested** | `tests/security/test_audit.py::TestEventsRecorded` — asserts the correct event type for create, first read, second read, and unknown id. `tests/security/test_audit_db.py::TestAuditPersistence` — asserts the row actually lands in PostgreSQL with the expected fields. |
| **Limitations** | Only secret create and reveal are instrumented. `expired` is never emitted: Redis TTL expiry is silent, so detecting it needs keyspace notifications or a sweeper, neither of which exists. `actor_user_id` is always NULL: the routes do not pass the caller's account, and secret creation is unauthenticated (R-07). |

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
| **Relevance** | Brief §2 requires error handling that does not expose sensitive information, and SR-09 requires generic error responses with no variation between failure causes. The same reasoning already applied to secrets under invariant 5 — a missing and a burned secret are indistinguishable — was not applied to authentication, leaving the inconsistency on the one endpoint that guards every other one. |
| **Implementation** | `app/core/auth.py` returns a single module-level constant `_INVALID_TOKEN_DETAIL = "Invalid or expired token"` from both 401 paths, so the two branches are textually identical and cannot drift apart. The diagnostic detail is not discarded: each handler logs it to `secretshare.auth` at WARNING before raising, recording the exception type and message but never the token itself, since a bearer token is a live credential (invariant 6). The previously silent `except Exception` now logs via `logger.exception`, so an unexpected 503 is no longer undebuggable. `WWW-Authenticate: Bearer` is unchanged across all rejections. |
| **How tested** | `tests/security/test_auth_error_disclosure.py` — six distinct failure modes (expired, wrong audience, unknown kid, malformed, empty segments, tampered signature) are asserted to produce **byte-identical** response bodies, not merely equal status codes. A parametrised test asserts no PyJWT vocabulary (`signing key`, `kid`, `audience`, `signature`, `algorithm`, `PyJWK`, `Unable to find`) appears anywhere in any response. Two tests assert the reason *is* present in the server log via `caplog`, so the fix suppresses disclosure without destroying operator diagnostics, and one asserts the bearer token — and separately its signature segment — never reaches the log at any level. 13 tests, all passing. |
| **Limitations** | **Timing is not addressed and remains a potential oracle.** Measured over 30 requests per case against the test client, an expired token and an unknown `kid` were indistinguishable (median 2.11 ms vs 2.05 ms) — but only because the test JWKS is pre-cached in memory. In production an unrecognised `kid` can miss `PyJWKClient`'s cache and trigger a network fetch from Keycloak, which would make that path far slower than a locally-detected expiry and reintroduce the distinction the constant body removes. This has not been measured against a live Keycloak, so the control is verified for response *content* only. Closing it requires constant-time handling of the whole validation path and was explicitly out of scope here. The 503 for an unreachable Keycloak is also still distinguishable from a 401, which tells a prober about infrastructure state rather than about their token. Log volume is a second-order concern: a token-guessing attack now writes one WARNING per attempt, which is useful for detection but unbounded, and rate limiting rather than this control is what should bound it. |

### AUTH-2 — Access token verification

| | |
|---|---|
| **Security problem** | An API that accepts a token without checking its signature, algorithm, audience and expiry accepts forged tokens, tokens issued for another client, and tokens that have expired. Accepting `alg: none` or letting the token choose between RS256 and HS256 allows a forger to sign with the public key. |
| **Relevance** | The caller's identity decides who may reveal a secret (AUTH-3) and for whom a device key is registered. A forged identity on `POST /keys/register` would register an attacker's public key for the victim, so later secrets addressed to the victim would be wrapped for the attacker. |
| **Implementation** | `app/core/auth.py::get_current_user`, used as a FastAPI dependency. `HTTPBearer` extracts the token; a missing header returns 403. `PyJWKClient` fetches the realm key set from `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/certs` and caches it for 3600 seconds; the key is selected by the token's `kid`. `jwt.decode` is called with the fixed list `algorithms=["RS256"]` and `audience=KEYCLOAK_CLIENT_ID`; PyJWT verifies `exp` when present. The audience claim is added by the `secretshare-api-audience` mapper in `keycloak/realm-export.json`. The caller identity is `preferred_username`, or `sub` when that claim is absent. An unreachable key set returns 503. |
| **How tested** | `tests/test_api.py::TestMeEndpoint` — valid token accepted; missing token 403; expired token, wrong audience, unknown `kid` and a malformed token each 401; unreachable Keycloak 503. `tests/test_keys.py::test_register_without_token_fails_403`. `tests/test_oauth_integration.py` obtains real tokens from Keycloak and calls the API; it runs in the `oauth-integration` job of `test-api.yml` against the full compose stack. |
| **Limitations** | **The issuer is not verified**: `jwt.decode` receives no `issuer`, although the key set is realm-specific, which limits the practical effect (R-16). `exp`, `iat` and `nbf` are verified only when present, not required. Tokens are not introspected, so a token remains valid until it expires after the user is disabled or signs out (5 minutes, the realm default). The key set is fetched over HTTP on the internal network (R-13). A rename in Keycloak changes `preferred_username` and orphans the user's secrets and device keys. |

### AUTH-3 — Reveal bound to the recipient's identity

| | |
|---|---|
| **Security problem** | When the identifier of an object is enough to retrieve it, anyone who obtains the identifier obtains the object (insecure direct object reference). |
| **Relevance** | A share link travels through chat and mail. It is seen by link previewers, forwarded, pasted into the wrong channel, and kept in clipboard histories. If the link were the only credential, each of those copies could read the secret. |
| **Implementation** | `POST /secrets/reveal` (`app/api/routes/secrets.py::reveal_secret`) depends on `get_current_user` (AUTH-2). The caller identity is passed to `SecretService.retrieve_secret`, which compares it with the envelope's `recipient_id` inside the atomic burn (SEC-1). A mismatch returns 403 with a constant message, records a `denied` audit event and leaves the secret stored. A token without `preferred_username` or `sub` returns 400. |
| **How tested** | `tests/test_secrets.py::test_retrieve_secret_unauthorized_recipient` and `TestDeniedRevealKeepsSecret` — a denied attempt returns 403, repeated denials never delete the secret, and the recipient can still reveal it afterwards. `tests/security/test_secrets_invariants.py::TestDeniedRevealIsNonDestructive::test_route_denies_then_serves_recipient` runs the same sequence against a real Redis. The preview smoke test (`.github/scripts/test_secret_lifecycle.sh`) addresses a secret to a non-existent user and verifies that `testuser` receives 403. |
| **Limitations** | A signed-in non-recipient learns from the 403 that the secret exists; this is accepted, because `POST /secrets/exists` answers the same question. The binding compares user name strings; it is not bound cryptographically to the ciphertext. Only reveal is authorised: `POST /secrets`, `POST /secrets/exists` and `GET /keys/{user_id}` accept anonymous calls (R-06, R-07). The realm has only one test user, so the smoke test cannot yet exercise a denial by a real second account. |

---

## Secret lifecycle

### SEC-1 — Atomic, recipient-checked burn

| | |
|---|---|
| **Security problem** | Burn-after-read built from separate read and delete steps has two failure modes. Reading, checking and then deleting lets two concurrent requests both read the secret before either deletes it. Deleting first and checking afterwards destroys the secret when the wrong person asks for it. |
| **Relevance** | Single delivery is the product's core guarantee (invariant 3). The second failure mode existed in the project: an earlier handler used `GETDEL` before comparing the recipient, so a wrong recipient received 403 and the real recipient then found the secret gone. It was fixed in PR #26. |
| **Implementation** | `app/storage/redis_store.py::SecretStore.burn_for_recipient` runs one Lua script with `EVAL`. The script reads `s:<payload_id>`, decodes it with `pcall(cjson.decode, …)`, compares `recipient_id` with the caller identity passed in `ARGV[1]`, and deletes the key only on a match. It returns `missing`, `denied` or `burned`. Redis runs a script without interleaving other commands, so the three steps form one operation. The payload id and the identity are passed as `KEYS` and `ARGV`, never concatenated into the script. A payload that is not a JSON object with a matching recipient is never deleted by this path. |
| **How tested** | `tests/security/test_secrets_invariants.py`, against a real Redis: `TestAtomicBurn::test_burn_is_single_delivery` (20 concurrent reveals by the recipient, repeated 5 times; exactly one succeeds each time) and `test_second_read_is_a_miss`; `TestDeniedRevealIsNonDestructive::test_denied_reveal_leaves_key_and_ttl`, `test_concurrent_intruders_cannot_starve_the_recipient` (10 wrong-user requests race 10 recipient requests; exactly one recipient request receives the secret), `test_unparseable_payload_is_never_deleted`. CI sets `TEST_REDIS_URL` and fails the job if any security test is skipped. `tests/fakes.py::InMemorySecretStore` mirrors the script for unit tests. |
| **Limitations** | The server deletes the envelope before the browser attempts decryption. A reveal on a browser without a matching device key destroys a secret that can no longer be read (R-05). The guarantee assumes a single Redis primary; replication to replicas is asynchronous and is not used. |

### SEC-2 — Bounded lifetime and non-persistent store

| | |
|---|---|
| **Security problem** | A secret that is never read would otherwise remain stored indefinitely. A store that writes snapshots or an append-only file to disk leaves copies of envelopes in volumes and backups after the secret has been read. |
| **Relevance** | The purpose of the relay is to shorten the lifetime of a shared credential. An unread secret addressed to a contractor who never opens it must disappear without manual action, and no copy may survive in a disk image. |
| **Implementation** | `SecretStore.put` writes with `SET … EX <ttl>`. The lifetime defaults to `SECRET_TTL_SECONDS` (600) and must lie within `SECRET_TTL_MIN_SECONDS` (300) and `SECRET_TTL_MAX_SECONDS` (86400). The bounds are checked three times: `Settings` refuses to start when the default lies outside them; the request schema rejects an out-of-range `ttl_seconds` with 422; `SecretService.create_secret` checks again against the live settings. Redis runs with `--save "" --appendonly no` in `docker-compose.yml` and `docker-compose.preview.yml`, so it writes neither RDB snapshots nor an AOF. |
| **How tested** | `tests/security/test_secrets_invariants.py::TestTtl` — the TTL is set on the Redis key, a requested TTL reaches Redis, and a TTL above the maximum never reaches Redis. `tests/test_secrets.py::TestTtl` — default, explicit `null`, custom value, `expires_at` and out-of-range rejection. `tests/test_config.py::TestTtlBounds` — invalid bounds stop startup. |
| **Limitations** | No test inspects the running Redis configuration (`CONFIG GET save`); the setting exists only on the compose command line. Expiry is silent, so no `expired` audit event is recorded (AUD-1). A restart of Redis deletes all unread secrets, which is the accepted cost of not persisting them. Redis has no `maxmemory` ceiling (R-21). |

### SEC-3 — Unguessable payload identifiers

| | |
|---|---|
| **Security problem** | Sequential or weakly random identifiers can be guessed or enumerated. |
| **Relevance** | The identifier locates a secret and is carried in the share link. A guessable identifier would let an attacker probe for existing secrets and target them. |
| **Implementation** | `app/core/ids.py::new_payload_id` returns `secrets.token_urlsafe(32)`: 32 bytes from the operating system's CSPRNG, encoded as 43 base64url characters. It is the only source of payload identifiers (invariant 4). With N stored secrets and q guesses, the probability of a hit is at most N·q / 2²⁵⁶. |
| **How tested** | `tests/security/test_secrets_invariants.py::TestPayloadIds::test_payload_id_entropy` — 10 000 identifiers, no collision, each at least 43 characters. |
| **Limitations** | The test checks uniqueness and length, not the randomness source; the source is enforced by code review of `core/ids.py`. Identifier strength does not help once an identifier is disclosed (R-04); AUTH-3 limits what a holder can do with it. |

### SEC-4 — Uniform response for unknown, burned and expired secrets

| | |
|---|---|
| **Security problem** | Distinct responses for "never existed", "already read" and "expired" tell a prober which identifiers once held a secret and whether it was read. |
| **Relevance** | Invariant 5. A sender or an attacker must not learn from the API whether a recipient already read a secret, and a guessed identifier must not be confirmable as historical. |
| **Implementation** | The burn script returns `missing` for all three cases, because Redis does not distinguish an expired key from an absent one. `SecretService` raises one `SecretNotFoundError`; `app/api/errors.py` maps it to 404 with the constant body `Secret not found or already retrieved`. There is no expired error type. `POST /secrets/exists` returns `{"exists": false}` for all three cases. Audit failures are swallowed so that they cannot change the response (AUD-4). |
| **How tested** | `tests/security/test_secrets_invariants.py::TestNoEnumerationOracle::test_missing_and_burned_are_identical` — status, headers and body of a burned and an unknown id are compared. `tests/test_secrets.py::TestDomainExceptionHandlers::test_burned_and_unknown_are_indistinguishable` and `TestDeniedRevealKeepsSecret::test_burn_after_reveal_is_still_404_for_everyone`. `TestSecurityHeaders::test_headers_present_on_a_miss_too`. |
| **Limitations** | Equality is verified for content, not for timing (R-22). A signed-in non-recipient receives 403 for a stored secret, which differs from 404 by design (AUTH-3). |

---

## API hardening

### API-1 — Request body size limit

| | |
|---|---|
| **Security problem** | Pydantic enforces field lengths only after the whole body has been read into memory. An unauthenticated client could make the API buffer an arbitrarily large request. |
| **Relevance** | `POST /secrets` accepts anonymous requests. Without an early limit, a few large requests exhaust API memory, and oversized envelopes would reach Redis. |
| **Implementation** | `app/core/limits.py::BodySizeLimitMiddleware`, a raw ASGI middleware placed outside every other layer except the proxy resolver. The limit is `MAX_PAYLOAD_BYTES` (65536) plus 1024 bytes for the JSON structure. A declared `Content-Length` above the limit is rejected with 413 before the body is read; an unparsable `Content-Length` returns 400. The body is also counted as it streams, so a chunked or understated request is cut off and answered with 413. `SecretCreateRequest` checks the ciphertext again in UTF-8 bytes, so a payload one byte over the limit returns a schema 422. |
| **How tested** | `tests/security/test_secrets_invariants.py::TestPayloadSizeLimit` — a ciphertext of 65 537 bytes is rejected with 413 or 422 and nothing is written to Redis; a ciphertext of exactly 65 536 bytes is accepted. `tests/test_secrets.py::TestPayloadSize` — at limit, over limit, empty. |
| **Limitations** | The tests exceed the schema limit by one byte and accept either status. **No test sends a body above the middleware limit or a chunked body**, so the 413 path of the middleware is verified by review only. The limit applies per request, not per client (see API-3). Traefik sets no body limit of its own. |

### API-2 — Schema validation without input echo

| | |
|---|---|
| **Security problem** | Unvalidated input reaches business logic and storage. Default validation errors in FastAPI repeat the rejected value in the response, which returns ciphertext or payload ids to whoever triggered the error and into any log that records response bodies. Unhandled exceptions can expose stack traces. |
| **Relevance** | Brief §2 requires validation of all input and error handling that does not expose sensitive information. The rejected value on these endpoints is ciphertext or a payload id. |
| **Implementation** | Every request body is a Pydantic model in `app/schemas/`: `recipient_id` 1–255 characters; `encrypted_keys` at least one item, each with a UUID `device_id`; `iv` at most 64 characters; `ciphertext` limited in UTF-8 bytes; `ttl_seconds` within bounds; `payload_id` 1–128 characters; `public_key` matched against an SPKI PEM pattern and limited to 4096 characters; `platform` from an allowlist; `label` at most 64 characters. `app/api/errors.py::_request_validation` returns only `type`, `loc`, `msg` and `ctx` for each error and drops `input`. `app/main.py::unhandled_exception_handler` returns a constant 500 body and logs the exception server-side. |
| **How tested** | `tests/test_secrets.py::test_check_exists_validates_payload_id`, `TestTtl::test_ttl_out_of_bounds_is_rejected`, `TestPayloadSize::test_empty_payload_is_rejected`; `tests/test_keys.py::test_register_invalid_pem_fails_422`; `tests/test_api.py::TestErrorHandling::test_unhandled_exception_returns_500_without_leaking_traceback`. |
| **Limitations** | **No test asserts that a 422 body omits the rejected input.** The API does not check that `iv`, `ciphertext` and `encrypted_aes_key` are valid base64 or that the IV has 12 bytes; this follows from invariant 1, and malformed envelopes fail only at decryption. The PEM pattern checks format, not key type or size. The 404 of `GET /keys/{user_id}` repeats the requested user name. |

### API-3 — Rate limiting

| | |
|---|---|
| **Security problem** | Without a request limit, a client can flood the store with envelopes, probe identifiers at high speed, or use the API to amplify load on Redis and PostgreSQL. |
| **Relevance** | `POST /secrets` and `POST /secrets/exists` accept anonymous calls, and every create writes up to 64 KB to Redis memory. |
| **Implementation** | `app/core/rate_limit.py::RateLimiter`, a FastAPI dependency implementing a fixed-window counter in Redis: `INCR rl:<scope>:<client ip>`, `EXPIRE` on the first request of the window, 429 with `Retry-After` set to the remaining window when the count exceeds the limit. `POST /secrets` uses scope `secrets:create` with `CREATE_RATE_LIMIT` (10 per 60 seconds). `POST /secrets/exists` and `POST /secrets/reveal` share scope `secrets:retrieve` with `RETRIEVE_RATE_LIMIT` (30 per 60 seconds). Limits are read from `Settings` on each request. The client address comes from API-4. |
| **How tested** | `tests/test_config.py::TestRoutesUseSettings::test_create_rate_limit_comes_from_settings` and `test_retrieve_rate_limit_comes_from_settings` — the limit is enforced with the configured value. `tests/test_proxy.py::TestRateLimitPerRealClient` — separate buckets per client, and a forged `X-Forwarded-For` does not reset a bucket. |
| **Limitations** | The limiter **allows requests when Redis fails**, logging `Rate limiting skipped` (R-21). A fixed window admits up to twice the limit across a window boundary. Limits are per IP address: clients behind one NAT share a bucket, and a distributed client is not limited. `GET /keys/{user_id}`, `POST /keys/register` and Keycloak logins are not limited (R-03, R-06). `INCR` and `EXPIRE` are separate commands; if `EXPIRE` fails after `INCR`, the counter has no expiry and the address stays limited until the key is deleted. |

### API-4 — Client address resolution behind proxies

| | |
|---|---|
| **Security problem** | Behind a reverse proxy the TCP peer is the proxy. Using it as the client address puts all users into one rate-limit bucket and records the proxy's address in the audit log. Trusting `X-Forwarded-For` from any peer, or taking its left-most entry, lets a client choose its own address. |
| **Relevance** | Before PR #29 every caller in an environment shared the limit of 10 creations per minute, and audit rows held Traefik's address, which made both API-3 and the audit IP field ineffective. |
| **Implementation** | `app/core/proxy.py::TrustedProxyMiddleware`, the outermost middleware. When the TCP peer lies in `TRUSTED_PROXIES`, it reads `X-Forwarded-For` from right to left and takes the first entry that is not a trusted proxy; entries further left are ignored. A malformed chain leaves the peer unchanged. `X-Forwarded-Proto` is applied under the same condition. Both compose files set `TRUSTED_PROXIES` to the private ranges `10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`. Uvicorn runs with `--no-proxy-headers`. The preview Traefik runs with `forwardedHeaders.trustedIPs` for the same ranges so that it keeps the address set by the Tailscale sidecar. |
| **How tested** | `tests/test_proxy.py` — `TestClientResolution` (trusted and untrusted peers, spoofed left-most entry, malformed chain, IPv6), `TestScheme`, `TestTrustedProxiesSetting` (an invalid CIDR stops startup), `TestRateLimitPerRealClient`, and `TestDeploymentWiring`, which asserts the compose files, the Dockerfile and the preview workflow carry the required settings. |
| **Limitations** | All private ranges are trusted. The result is correct only while every hop in those ranges is a proxy that overwrites or appends `X-Forwarded-For` correctly; a client that reaches the API directly from a private network could supply its own header. The API port is not published, which prevents this in the current compose files. |

### API-5 — API response security headers

| | |
|---|---|
| **Security problem** | Responses without cache, framing and content-type directives can be stored by caches, rendered as HTML, or framed by another site. |
| **Relevance** | A reveal response contains an envelope that must not outlive the burn in a browser or proxy cache. |
| **Implementation** | `app/core/headers.py::SecurityHeadersMiddleware` sets on every response: `Cache-Control: no-store, no-cache, must-revalidate, private`, `Pragma: no-cache`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `Cross-Origin-Resource-Policy: same-origin`, `Cross-Origin-Opener-Policy: same-origin` and a restrictive `Permissions-Policy`. Headers are applied with `setdefault`, so a route can override one deliberately. Swagger UI paths receive a separate policy that allows its assets. CORS admits only the origins in `ALLOWED_ORIGINS`. |
| **How tested** | `tests/test_api.py::TestSecurityHeaders` — strict policy on a normal route, relaxed policy on the documentation route. `tests/security/test_secrets_invariants.py::TestSecurityHeaders` — a reveal response is not cacheable, and headers are present on a 404. `tests/test_api.py::TestCORS`. |
| **Limitations** | No HSTS; it belongs at the TLS edge (R-12). The documentation policy allows `'unsafe-inline'` scripts and `https://cdn.jsdelivr.net`, and Swagger UI is reachable in every environment. The documentation check matches any path containing `/docs`. |

---

## Transport and storage

### TLS-1 — TLS between the API and the data stores

| | |
|---|---|
| **Security problem** | Unencrypted connections to Redis and PostgreSQL expose envelopes, database credentials, device keys and audit data to anyone who can observe or modify traffic on the network between containers or hosts. |
| **Relevance** | Brief §1 requires encryption in transit. The envelope is already encrypted, but the database password and the audit data are not. |
| **Implementation** | The `tls-init` service runs `tls/generate.sh` once per `tls-certs` volume: an RSA 4096 certificate authority and RSA 4096 server certificates with `CN=db` and `CN=redis`, signed with SHA-256, valid for 3650 days; private keys mode 600. Redis listens only on its TLS port (`--tls-port 6379 --port 0`). PostgreSQL runs with `ssl=on`. The API connects to Redis with `rediss://`, `ssl_ca_certs` and `ssl_cert_reqs="required"`, and to PostgreSQL with an SSL context built from the same CA, including during Alembic migrations. Keycloak and the initialisation job connect to PostgreSQL with `sslmode=require`. Redis and PostgreSQL ports are published on `127.0.0.1` only. |
| **How tested** | `tests/test_tls.py`, run by the `test-tls.yml` workflow: `TestTlsSettings`, `TestCreateEngineSSL` (SSL context present, certificate verification required), `TestRedisSSLContext` (verification required, invalid CA rejected), `TestGenerateScript` (files created, key modes 600, certificate subjects, issuer, idempotence). |
| **Limitations** | **Host names are not verified**: the certificates carry no subject alternative name and both clients set `check_hostname` to false, so any certificate issued by the internal CA is accepted for either service. Keycloak's `sslmode=require` encrypts without verifying the certificate. PostgreSQL does not require TLS from clients. TLS is not mutual, and Redis has no password or ACL user (`--tls-auth-clients no`). The CA has no rotation procedure. Traffic from Traefik to the services and from the API to the Keycloak key set uses HTTP (R-13). |

### DB-1 — Parameterised data access

| | |
|---|---|
| **Security problem** | SQL built by string concatenation lets input change the query (SQL injection). The same applies to Redis scripts built from input. |
| **Relevance** | `GET /keys/{user_id}` places a caller-supplied string into a database query without authentication; `POST /secrets/reveal` passes a caller-supplied payload id and identity to a Redis script. |
| **Implementation** | All SQL is issued through SQLAlchemy 2.0 constructs (`select`, `update`, ORM inserts) in `app/services/keys.py` and `app/core/audit.py`; values are sent as bound parameters by the asyncpg driver. Migrations contain static DDL only. Redis keys are formed as `s:<payload_id>` and passed as command arguments; the burn script receives the key in `KEYS` and the identity in `ARGV`. |
| **How tested** | Indirectly: `tests/test_keys.py::test_register_and_retrieve_keys_flow` and `tests/security/test_audit_db.py` exercise the queries. **No test submits injection payloads.** |
| **Limitations** | Protection rests on the absence of raw SQL, which is enforced by review rather than by a linter or test. A future `text()` query with string formatting would not be detected automatically. |
