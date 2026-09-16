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
| **Implementation** | `audit_events` table in PostgreSQL. `app/core/audit.py::AuditService.record` writes one row per event. `POST /secrets` records `created`; `GET /secrets/{id}` records `revealed` on a hit and `denied` on a miss. Rows carry event type, an 8-character payload id prefix, actor, IP, user agent, and a server timestamp. |
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

---

## Open finding

### AUD-6 — The full payload id is written to the web server access log

**Status: open, not fixed on this branch. Found while testing AUD-2.**

| | |
|---|---|
| **Security problem** | The audit table stores only an 8-character prefix, but the payload id travels in the URL path of `GET /secrets/{id}`. Uvicorn's access log records the full request line, so the complete 43-character id — a working capability to read the secret — lands in plaintext logs. |
| **Relevance** | Directly contradicts invariant 6, and it defeats AUD-2: truncating the id in the database achieves little while the same id sits in the log next to it. Anyone with log access, including shipped or backed-up logs, can read secrets that have not yet been burned. |
| **Evidence** | Observed during end-to-end testing: `INFO: 127.0.0.1 - "GET /secrets/<43-character id> HTTP/1.1" 200 OK`. Confirmed the id in the log matched the live secret, while `audit_events` correctly held only the 8-character prefix. |
| **Cause** | Pre-existing, from the Step 1 URL design. Not introduced by the audit work. |
| **Possible fixes** | Move the id out of the path — send it in a header or request body on a `POST`-style reveal; or disable the uvicorn access log in production; or put a path-rewriting log filter in front. The first is the only one that also protects proxy, Traefik, and browser-history copies of the URL. Each has trade-offs and needs a team decision, so it is recorded here rather than patched silently. |

---

## Notes on scope

Controls for atomic burn, TTL purge, ciphertext-only relay, CSPRNG payload IDs,
timing-safe 404, and Redis persistence disabled are required by CLAUDE.md §11.9 and
are **not yet written up here**. They belong to the Step 1 and Step 5 work and
should be added as rows in this same format.
