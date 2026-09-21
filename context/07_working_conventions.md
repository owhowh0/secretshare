# Working Conventions (for humans and AI assistants)

How changes are made, verified and merged in this repository.

---

## 1. Verify on the Server, Not Locally

The team verifies changes on real preview environments rather than a local Docker stack:

1. Branch from `main`, commit, push, and open a PR.
2. CI (`test-api.yml`, `test-tls.yml`) runs the test suites.
3. `deploy-preview.yml` builds the PR on `staging-server` and runs the smoke battery against `https://pr-<N>.<tailnet>.ts.net`.
4. Check the live preview directly as well (see §2).

Local runs are fine for quick iteration, but "it works" means green CI and a green preview.

### Reading CI
- Use `gh pr checks <N>` and `gh run view <id> --log`.
- **A green deploy is only meaningful if the smoke tests actually ran.** Look for `=== Preview deployment and all verification tests passed successfully! ===` in the log. Since PR #26 the step fails when that line is missing (see troubleshooting §9).

---

## 2. Access to the Staging Server

- The server is only reachable over **Tailscale**. Your node must be allowed by the tailnet ACL and show `staging-server` in `tailscale status`.
- For direct inspection, use `ssh devuser@staging-server`. Containers are named `pr-<N>-<service>-1` (e.g. `pr-26-api-1`, `pr-26-redis-1`, `pr-26-db-1`).
  - Useful read-only checks: `docker ps`, `docker logs pr-<N>-api-1`, `docker exec pr-<N>-redis-1 redis-cli ttl s:<id>`, `docker exec pr-<N>-db-1 psql -U secretshare -d secretshare_pr_<N> -c '...'`.
  - Destructive actions on the server (`docker stop`, `docker start`, `git reset`) need the owner's explicit OK.
- The CI deploy itself uses `tailscale ssh root@staging-server`.

---

## 3. Tests

- Every behavior change needs tests in `api/tests/`. Put security properties in `api/tests/security/`; CI **fails if any security test is skipped**.
- Use the shared helpers in `api/tests/fakes.py` instead of hand-rolled fakes:
  - `make_secret_service(store?, settings?)`: the real `SecretService` over `InMemorySecretStore`.
  - `secret_body(ciphertext, recipient_id=..., **extra)`: a valid `POST /secrets` body.
  - `recipient_claims(username)`: an override for `get_current_user`.
- Redis- and Postgres-backed tests need `TEST_REDIS_URL` / `TEST_DATABASE_URL` (CI provides both).
- `tests/test_tls.py` runs only in `test-tls.yml`; `test-api.yml` ignores it.
- **When an API contract changes, update every test, the smoke scripts in `.github/scripts/`, and the web client in the same PR.** PR #22 changed the create/reveal contract without doing this, which left 21 tests red on `main` and the smoke tests silently out of date.

---

## 4. Git & PR Conventions

- Commits follow Conventional Commits: `feat(api): ...`, `fix(ci): ...`, `docs(context): ...`.
- **Don't add `Co-Authored-By: Claude` trailers** or "Generated with Claude Code" footers.
- Merge with merge commits (`gh pr merge --merge --delete-branch`).
- **Stacked PRs:** deleting a base branch on merge **closes** the stacked PR instead of retargeting it (this happened with #20). Retarget the child PR to `main` *before* merging its parent, or merge without `--delete-branch` and delete the branch afterwards.

---

## 5. Windows Development Notes

- `.gitattributes` pins `*.sh` to LF. Without it, `core.autocrlf=true` produced `/bin/bash^M: bad interpreter` in `init-db/*.sh` and Postgres exited with code 126.
- In Git Bash, `-v /var/run/docker.sock:...` gets rewritten to a Windows path. Run such `docker run` commands from PowerShell.
- To run the smoke scripts from Windows, use `tr -d '\r' < script.sh | bash -s <args>`.
