# Project Context & Knowledge Base

Technical context, decisions, solved problems and open issues for **SecretShare**. If you're picking up this repository (human or AI assistant), read these before making changes. Last updated **2026-09-21** (through PR #27).

## What SecretShare is

A one-time secret relay with **end-to-end encryption**. A signed-in sender addresses a secret to a Keycloak user. The browser encrypts it (AES-256-GCM, with the key wrapped by RSA-OAEP for each of the recipient's devices) and the API stores only the encrypted envelope in Redis with a TTL. The recipient reveals it once: the API checks that the caller is the recipient and deletes the envelope atomically, and the browser decrypts it locally.

Stack: Next.js 15 + NextAuth v5 · FastAPI · Redis 7 (TLS) · PostgreSQL 16 (TLS, audit log and device keys) · Keycloak 26 · Traefik · Tailscale (HTTPS previews).

## Index

| File | Read it when you're... |
| :--- | :--- |
| [`01_architecture_and_routing.md`](01_architecture_and_routing.md) | touching compose files, Traefik routing, internal TLS, `Settings` |
| [`02_authentication_and_keycloak.md`](02_authentication_and_keycloak.md) | touching login, tokens, the realm, or which endpoints require auth |
| [`03_troubleshooting_and_edge_cases.md`](03_troubleshooting_and_edge_cases.md) | debugging anything; it's a log of every non-obvious failure and its fix, including open ones |
| [`04_ci_cd_and_deployment.md`](04_ci_cd_and_deployment.md) | touching workflows, preview deploys, smoke scripts, staging |
| [`05_roadmap_and_next_steps.md`](05_roadmap_and_next_steps.md) | planning work: constraints, completed PRs, known issues, ideas |
| [`06_secret_lifecycle_and_e2e_encryption.md`](06_secret_lifecycle_and_e2e_encryption.md) | touching secrets, keys, the Redis store, or the web crypto; also the API reference and invariants |
| [`07_working_conventions.md`](07_working_conventions.md) | about to make a change: how to verify on the server, test helpers, git/PR rules |

## Current Status (2026-09-21)

- `main` is green: `Test API` and `Test TLS` pass. Every PR gets a live preview at `https://pr-<N>.tail070378.ts.net`, and its smoke battery now really runs (it silently didn't before #26).
- Recent: #26 fixed "a denied reveal burns the secret"; #27 moved `exists` out of the URL; #29 made rate limits per real client behind the proxies.
- **Open problems:**
  - staging deploy broken (troubleshooting §13)
  - decrypt-after-burn loss on unregistered devices (roadmap §3)

## Keep this folder current

Update these files in the same PR as the change they describe. This applies especially to the API reference (06 §2), the smoke battery (04 §4), known issues (05 §3), and any new failure mode worth a troubleshooting entry (03).
