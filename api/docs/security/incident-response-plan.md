# Incident response plan

This plan defines how the SecretShare team detects, contains and recovers from
security incidents, and how it records what was learned. The phases follow the
incident handling life cycle of NIST SP 800-61 Rev. 2: preparation; detection and
analysis; containment, eradication and recovery; post-incident activity.

Applies to: local development stacks, per-pull-request preview environments and
the staging server. No production environment exists; the plan is to be revised
before one is created.

---

## 1. Definitions

| Term | Meaning |
|---|---|
| Security event | An observable occurrence relevant to security, for example a rejected token or a denied reveal. |
| Security incident | An event, or a series of events, that violates or threatens a security requirement in `security-requirements.md`. |
| Payload identifier | The 43-character value that locates a secret. Its first 8 characters (the prefix) are recorded in the audit log. |

## 2. Roles

One person may hold more than one role. Names are assigned by the team and
recorded in section 2.2 before the plan is used.

### 2.1 Responsibilities

| Role | Responsibilities |
|---|---|
| Incident Coordinator | Declares the incident and its severity, assigns roles, decides on containment actions that affect availability, closes the incident. Default holder: the team's security owner. |
| Technical Lead | Investigates the affected component, performs containment and recovery steps, preserves evidence. Default holder: the owner of the affected component (backend, frontend or DevOps). |
| Investigator | Queries logs and the audit table, builds the timeline, identifies affected secrets and users. |
| Communications Lead | Informs affected users, the company mentor and, where required, the university internship coordinator. Approves every external message. |
| Scribe | Keeps the incident log: time-stamped actions, decisions and evidence locations. |

### 2.2 Contacts

| Role | Name | Contact | Deputy |
|---|---|---|---|
| Incident Coordinator | | | |
| Technical Lead (backend) | | | |
| Technical Lead (frontend) | | | |
| Technical Lead (DevOps) | | | |
| Communications Lead | | | |
| Company mentor | | | — |
| University internship coordinator | | | — |

### 2.3 Communication rules

1. Incident communication uses a dedicated team channel. If that channel may be
   compromised, the team switches to a separate channel agreed in advance.
2. Payload identifiers, tokens, passwords and keys are never pasted into any
   channel. They are referred to by the 8-character prefix, by the key identifier,
   or by the name of the variable.
3. Only the Communications Lead sends messages outside the team.

## 3. Severity levels

| Level | Criteria | Examples | Start of response |
|---|---|---|---|
| SEV-1 | Confirmed or probable disclosure of secret plaintext or private keys; control of a server, the Keycloak administrator account or the CI pipeline by an attacker. | Modified JavaScript served to users; leaked `KEYCLOAK_ADMIN_PASSWORD` used by a third party. | Immediately; all roles assigned. |
| SEV-2 | Compromise of one user account; tampering with the audit log; disclosure of personal data from PostgreSQL without disclosure of secrets. | Successful login from an unknown location followed by reveals; audit trigger found disabled. | Within 4 hours. |
| SEV-3 | Attack attempts without confirmed success; degraded service; vulnerability with a known exploit path in a deployed component. | Burst of rejected tokens or denied reveals; rate limits reached by one source. | Within 1 working day. |
| SEV-4 | Vulnerability without an exploit path in the deployed configuration; policy violation without exposure. | Advisory for an unused function of a dependency. | Within 1 week. |

The Incident Coordinator raises the severity when new information warrants it and
lowers it only after the triggering condition is ruled out.

## 4. Preparation

### 4.1 Available detection sources

| Source | What it shows | Access |
|---|---|---|
| `audit_events` table | `created`, `revealed`, `denied` events with time, 8-character prefix, IP address and user agent | `docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'` |
| API log, logger `secretshare.auth` | `Token rejected: …` for every invalid token, with the reason | `docker compose logs api` |
| API log, logger `secretshare.audit` | `Audit write failed …` when an audit row is lost | `docker compose logs api` |
| API log, logger `secretshare.rate_limit` | `Rate limiting skipped …` when Redis errors disable the limiter | `docker compose logs api` |
| Uvicorn access log | Status codes, including `429` and `403` per client address | `docker compose logs api` |
| Browser console / CSP | Script blocked by the Content Security Policy | Reported by users; no reporting endpoint yet |
| GitHub | Workflow runs, Dependabot and security advisories once enabled | Repository settings |

### 4.2 Queries prepared in advance

Events for one secret, from a prefix reported by a user:

```sql
SELECT created_at, event_type, ip, user_agent
FROM audit_events
WHERE payload_id_prefix = '<8 characters>'
ORDER BY created_at;
```

Denied reveals per source in the last hour:

```sql
SELECT ip, count(*) AS denied
FROM audit_events
WHERE event_type = 'denied' AND created_at > now() - interval '1 hour'
GROUP BY ip
ORDER BY denied DESC;
```

State of the append-only trigger (expected: `O`, enabled):

```sql
SELECT tgname, tgenabled
FROM pg_trigger
WHERE tgrelid = 'audit_events'::regclass AND NOT tgisinternal;
```

Log lines that indicate an attack or a lost control:

```sh
docker compose logs --since 1h api \
  | grep -E 'Token rejected|Audit write failed|Rate limiting skipped|" 429 '
```

### 4.3 Known gaps in preparation

These gaps are tracked in `risk-register.md` and limit what the team can detect or
restore.

| Gap | Effect | Risk |
|---|---|---|
| Keycloak event logging is disabled. | Logins and failed logins cannot be reconstructed. | R-10 |
| No alerting. | Every source above must be checked manually. | R-10 |
| No PostgreSQL backup. | Audit history, device keys and Keycloak accounts cannot be restored after loss. | R-18 |
| API connects as the database owner. | Audit rows are evidence only if the trigger is shown to have stayed enabled. | R-09 |

## 5. Procedure

### 5.1 Detection and analysis

1. Whoever observes a possible incident informs the Incident Coordinator without
   delay and records the time of observation and the source.
2. The Incident Coordinator declares an incident or records the event as a false
   positive, assigns a severity (section 3) and assigns the roles.
3. The Scribe opens the incident log with: identifier (`INC-<YYYYMMDD>-<n>`),
   severity, time of detection, reporter, affected environment and commit.
4. The Investigator establishes scope: affected components, users, payload
   prefixes and time window, using the sources in section 4.1.
5. The Technical Lead preserves evidence before changing any component
   (section 5.5).

### 5.2 Containment

Containment limits further damage. The Incident Coordinator chooses the actions;
actions that make the service unavailable require the Coordinator's decision.

| Action | Effect | Command or location |
|---|---|---|
| Take the environment offline | Stops all access through the edge. | `docker compose stop traefik`; for a preview, close the pull request. |
| Disable a user account | Blocks new logins for the user. | Keycloak admin console, realm `secretshare`, user settings. |
| End a user's sessions | Ends Keycloak sessions. Existing access tokens remain valid until they expire (5 minutes). | Keycloak admin console, user sessions. |
| Revoke a user's device keys | New secrets can no longer be wrapped for the compromised device. | `UPDATE device_keys SET revoked_at = now() WHERE revoked_at IS NULL AND user_id = (SELECT id FROM users WHERE platform_user_id = '<user name>');` |
| Invalidate all web sessions | Every user must sign in again. | Replace `AUTH_SECRET`, then `docker compose up -d web`. |
| Invalidate all access tokens | Tokens signed with the old key are rejected. | Keycloak admin console: add a new realm RSA key and disable the old one; then restart the API with `docker compose restart api`, because the API caches the key set for up to one hour. |
| Delete all unread secrets | Removes every envelope from Redis. **Irreversible**; senders must send again. | `docker compose exec redis redis-cli --tls --cacert /certs/ca.crt -h redis FLUSHDB` |

Redis stores no data on disk. Restarting the `redis` container deletes every
unread secret and every rate-limit counter. It is a containment action in its own
right and is not used for troubleshooting during an incident.

### 5.3 Eradication

1. Remove the cause: revert or patch the code, update the dependency or image,
   correct the configuration.
2. Rotate every credential that the attacker could have read (section 6, PB-4).
3. Add an automated test that fails on the cause of the incident. The fix is
   merged only when that test passes in CI, consistent with how controls in
   `security-controls.md` are verified.

### 5.4 Recovery

1. Redeploy from a known commit through the normal pipeline, not by editing the
   running containers.
2. Verify: CI green, preview smoke tests pass, the audit trigger is enabled
   (section 4.2), headers and CSP are present on responses.
3. Monitor the sources in section 4.1 with increased frequency for 7 days.
4. The Incident Coordinator closes the incident when recovery is verified.

### 5.5 Evidence handling

Before any container is restarted or rebuilt, the Technical Lead collects:

```sh
mkdir -p incident-<id> && cd incident-<id>
git -C .. rev-parse HEAD                      > deployed-commit.txt
docker compose -f ../docker-compose.yml ps    > containers.txt
docker compose -f ../docker-compose.yml images > images.txt
docker compose -f ../docker-compose.yml logs --timestamps > compose-logs.txt
docker compose -f ../docker-compose.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t audit_events' > audit_events.sql
sha256sum * > SHA256SUMS
```

Evidence is stored outside the affected host, with access limited to the incident
roles. The collected files contain personal data (IP addresses, user agents) and
are deleted when the incident is closed and the report is accepted, unless a
legal obligation requires keeping them.

### 5.6 Post-incident activity

Within 5 working days of closure the Incident Coordinator holds a review and the
Scribe completes the report.

| Report field | Content |
|---|---|
| Summary | What happened, in two or three sentences. |
| Timeline | Detection, declaration, containment, eradication, recovery, closure, with times. |
| Scope | Affected components, users, payload prefixes, personal data. |
| Root cause | Technical cause and the reason existing controls did not prevent it. |
| Actions | Containment and recovery actions taken. |
| Follow-up | Changes to code, tests, `threat-model.md`, `risk-register.md` and this plan, each with an owner and a date. |

## 6. Playbooks

### PB-1 Payload identifiers or tokens found in logs

**Trigger.** A full 43-character identifier, a bearer token or ciphertext is found
in a log file, a log backup or a shared screenshot. Default severity: SEV-3; SEV-2
if the log was accessible to people outside the team.

1. Determine which log, since when, and who could read it.
2. For identifiers: query the audit prefix for each one (section 4.2). A secret
   with a `revealed` event is already deleted. For secrets still stored, inform the
   sender through the Communications Lead; the reveal still requires the
   recipient's account (AUTH-3), so the exposure is limited to the fact that the
   secret exists.
3. For tokens: tokens expire after 5 minutes. If the log is recent, end the
   affected users' sessions (section 5.2).
4. Delete or restrict the log copies. Find the code path that wrote the value,
   extend `RedactSecretPaths` or remove the value from the request line, and add a
   test in `api/tests/security/test_access_log.py`.

### PB-2 Modified or malicious client code

**Trigger.** Users report CSP violations or unexpected behaviour of the page; the
served JavaScript differs from the build of the deployed commit; an advisory
reports malicious code in a web dependency. Default severity: SEV-1.

1. Take the affected environment offline (section 5.2). Code that runs in the
   browser can read plaintext before encryption, so availability is secondary.
2. Preserve the served assets and the image (`docker compose images`, `docker save`).
3. Compare the served files with a clean build of the same commit and with the
   committed `web/bun.lock`.
4. Treat every secret created or revealed during the exposure window as disclosed.
   Identify them through the audit log and inform the senders, who must rotate the
   credentials they sent.
5. Treat device private keys used during the window as disclosed: revoke all
   device keys (section 5.2) and let users register new ones at next sign-in.
6. Rebuild from a clean commit with verified dependencies before bringing the
   environment back.

### PB-3 Compromised user account

**Trigger.** A user reports a login or a reveal they did not perform; logins from
unexpected addresses. Default severity: SEV-2.

1. Disable the account and end its sessions (section 5.2).
2. List secrets revealed by the account. The audit log does not yet record the
   actor (`actor_user_id` is empty), so correlate by IP address, user agent and
   time with the user's own report.
3. Inform the senders of the affected secrets; they rotate the credentials they
   sent.
4. Revoke the user's device keys; secrets still stored for that user are no longer
   readable by a new device and are either left to expire or deleted.
5. Reset the password; once available, require a second factor before re-enabling
   the account (R-03).

### PB-4 Leaked infrastructure credential

**Trigger.** A credential appears in a commit, a CI log, a chat or on an
unauthorised machine. Default severity: SEV-2; SEV-1 if use by a third party is
confirmed.

| Credential | Rotation | Side effects |
|---|---|---|
| `POSTGRES_PASSWORD` | `ALTER ROLE <user> PASSWORD '<new>';`, update `.env`, restart `api` and `keycloak`. | Short outage of API and login. |
| `KEYCLOAK_ADMIN_PASSWORD` | Change in the Keycloak admin console, update `.env`. Review admin changes to the realm since the leak. | None. |
| `AUTH_SECRET` | Replace in `.env`, restart `web`. | All users sign in again. |
| Keycloak realm signing key | See section 5.2, "Invalidate all access tokens". | All users sign in again. |
| Internal CA or service TLS keys | `docker compose down`, remove the `tls-certs` volume, `docker compose up -d`; `tls-init` issues new certificates. | Full restart. |
| `TS_AUTHKEY`, `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET` | Revoke in the Tailscale admin console, issue new values, update the GitHub repository secrets. | Previews and staging deploys fail until updated. |

After rotation, remove the credential from the location where it leaked. For git
history, rotation is mandatory; rewriting history does not remove copies that
were already cloned.

### PB-5 Server or database compromise

**Trigger.** Unexpected processes or files in a container; audit trigger disabled;
unexplained changes to `device_keys` or `users`. Default severity: SEV-1.

1. Preserve evidence (section 5.5), then take the environment offline.
2. Check the trigger state and compare `audit_events` with any exported copy. A
   disabled trigger means the audit log is no longer reliable evidence for the
   period since it was disabled.
3. Check `device_keys` for keys registered or changed without a matching user
   action. A substituted key allows the attacker to decrypt secrets wrapped for it
   (R-08): revoke all keys created during the suspected period.
4. Rotate all credentials (PB-4).
5. Rebuild all containers from images built from a known commit, with new volumes
   for `tls-certs`.

### PB-6 Abuse and denial of service

**Trigger.** Rate limits reached repeatedly, bursts of `denied` events, bursts of
`Token rejected`, or Redis memory growth. Default severity: SEV-3.

1. Identify sources with the queries in section 4.2 and the access log.
2. Block the sources at the edge or at the host firewall.
3. If the limiter reports `Rate limiting skipped`, restore Redis connectivity
   first: without it, the limits are not enforced.
4. Lower `CREATE_RATE_LIMIT` or `RETRIEVE_RATE_LIMIT` temporarily through `.env`
   and restart the API.
5. Bursts of failed logins against Keycloak are handled by PB-3 when an account
   is affected; brute-force protection is not yet enabled (R-03).

### PB-7 Vulnerability in a dependency or component

**Trigger.** Advisory for Python, npm, a container image, Keycloak, Traefik,
Redis or PostgreSQL. Severity from the reachability of the vulnerable code in the
deployed configuration.

1. Determine whether the vulnerable version is deployed (`api/requirements.txt`,
   `web/bun.lock`, `docker compose images`) and whether the vulnerable function is
   used.
2. If reachable, apply the fix or a documented workaround, rebuild and redeploy
   through CI.
3. If not reachable, record the reason in the incident log and schedule the update.
4. Search the logs for signs of exploitation during the exposure window; if found,
   continue with PB-5.

## 7. Notification

| Recipient | When | By |
|---|---|---|
| Senders of affected secrets | A secret may have been read by someone other than the recipient. They rotate the credential they sent. | Communications Lead |
| Affected users | Their account, session or device key was compromised. | Communications Lead |
| Company mentor | Any SEV-1 or SEV-2 incident. | Incident Coordinator |
| University internship coordinator | An incident affects project deliverables or data of people outside the team. | Incident Coordinator |
| Supervisory authority | A personal data breach under GDPR Art. 33 applies; notification within 72 hours of becoming aware. | Incident Coordinator, after assessment with the mentor |

## 8. Testing and maintenance

| Activity | Schedule |
|---|---|
| Tabletop exercise on PB-3 (compromised account) | October 2026 |
| Tabletop exercise on PB-4 (leaked credential), including a real rotation of `AUTH_SECRET` in a preview | November 2026 |
| Restore test, once backups exist (R-18) | November 2026, then monthly |
| Review of this plan | At each PBL milestone, after each incident, and before any production deployment |
