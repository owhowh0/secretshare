# Branch Protection Rules & CI Enforcement Evidence (T5)

## 1. Context & Motivation

Historically, `main` received direct pushes (8 direct commits out of 33) and PRs were merged with failing tests (e.g., PR #22 and PR #23 landed on `main` despite failing "Run tests" steps). Commit `a27bfae` was pushed directly to `main` and broke CI (run `35844926994`).

To prevent broken builds, test regressions, and unreviewed code from entering production, strict GitHub Branch Protection Rulesets are enforced on `main`.

---

## 2. Branch Protection Configuration (`main`)

### Rules Enforced:
1. **Require a pull request before merging:**
   - Direct pushes to `main` are strictly blocked (`git push origin main` rejected).
   - Require approvals before merging.
   - Dismiss stale pull request approvals when new commits are pushed.
2. **Require status checks to pass before merging:**
   - Status checks must be green:
     - `Run API tests` ([`test-api.yml`](../../../.github/workflows/test-api.yml))
     - `Run OAuth live integration tests` ([`test-api.yml`](../../../.github/workflows/test-api.yml))
     - `Run TLS tests` ([`test-tls.yml`](../../../.github/workflows/test-tls.yml))
     - `Secret scanning (Gitleaks)` ([`security.yml`](../../../.github/workflows/security.yml))
     - `Python dependency audit (pip-audit)` ([`security.yml`](../../../.github/workflows/security.yml))
     - `Frontend dependency audit (bun audit)` ([`security.yml`](../../../.github/workflows/security.yml))
   - **Require branches to be up to date before merging** (strict linear integration).
3. **Do not allow bypassing the above settings:**
   - Applies to administrators and all contributors alike.
4. **Block force pushes and branch deletions:**
   - Force pushes (`git push --force`) are permanently disabled on `main`.

---

## 3. Verification & Evidence

### Attempted Direct Push to `main`:
```bash
$ git push origin main
remote: error: GH006: Protected branch update failed for refs/heads/main.
remote: error: Changes must be made through a pull request.
remote: error: Required status checks must pass before merging.
To https://github.com/owhowh0/secretshare.git
 ! [remote rejected] main -> main (protected branch hook declined)
error: failed to push some refs to 'https://github.com/owhowh0/secretshare.git'
```

### Pull Request Status Check Gate:
All PRs targeting `main` must show green status indicators on all required jobs:
- `Test API / Run API tests` ✅
- `Test API / Run OAuth live integration tests` ✅
- `Test TLS / Run TLS tests` ✅
- `Security & Dependency Audit / Secret scanning (Gitleaks)` ✅
- `Security & Dependency Audit / Python dependency audit (pip-audit)` ✅
- `Security & Dependency Audit / Frontend dependency audit (bun audit)` ✅
