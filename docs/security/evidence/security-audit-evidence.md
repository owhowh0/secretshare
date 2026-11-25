# Security & Dependency Audit Evidence (T7)

## 1. Secret Scanning (Gitleaks)

- **Workflow**: [`.github/workflows/security.yml`](../../.github/workflows/security.yml) (`gitleaks` job)
- **Tool**: `gitleaks/gitleaks-action@v2` with full git history (`fetch-depth: 0`)
- **Configuration**: [`.gitleaks.toml`](../../.gitleaks.toml) (extends default rules, allowlisting known synthetic test keys in `api/tests/` and demo realm in `keycloak/`)
- **Status**: Clean — no real secrets or unredacted credentials detected across repository history.

## 2. Software Composition Analysis (SCA)

### Python API Dependencies (`pip-audit`)
- Scans `api/requirements.txt` against PyPI Advisory Database and OSV.
- Dependencies scanned:
  - `fastapi[standard]==0.115.6`
  - `redis==5.2.1`
  - `pydantic-settings==2.7.1`
  - `sqlalchemy[asyncio]==2.0.54`
  - `asyncpg==0.30.0`
  - `alembic==1.14.0`
  - `httpx==0.28.1`
  - `pyjwt[crypto]==2.10.1`
- **Result**: 0 known vulnerabilities found.

### Frontend Web Dependencies (`bun audit`)
- Scans `web/bun.lock` against npm / GitHub Advisory Database.
- Dependencies:
  - `next: ^15`
  - `next-auth: ^5.0.0-beta.32`
  - `react: ^19`
  - `react-dom: ^19`
- **Result**: 0 known vulnerabilities found.
