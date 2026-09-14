# Tailscale & Server Deployment Guide

This guide provides the step-by-step setup for running the SecretShare deployment pipeline using Tailscale SSH and Docker Compose.

---

## 1. One-Time Server Bootstrap

Run these commands as root/sudo on your remote Ubuntu/Debian server:

```bash
# Step 1: Install Docker & Docker Compose
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

# Step 2: Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Step 3: Connect Server to Tailnet with SSH enabled and tagged as 'tag:server'
tailscale up --ssh --advertise-tags=tag:server --hostname=staging-server

# Step 4: Create the shared unprivileged 'devuser' account for developers
useradd -m -s /bin/bash devuser
usermod -aG docker devuser

# Step 5: Initialize the application root directory
mkdir -p /opt/secretshare/worktrees
git clone git@github.com:owhowh0/secretshare.git /opt/secretshare

# Step 6: Create initial .env file
cp /opt/secretshare/.env.example /opt/secretshare/.env
```

---

## 2. Tailscale ACL Policy (Admin Console)

Navigate to **Tailscale Admin Console** $\rightarrow$ **Access Controls** and replace or merge with this configuration:

```json
{
  "tagOwners": {
    "tag:server": ["autogroup:admin"],
    "tag:ci": ["autogroup:admin"]
  },

  "groups": {
    "group:contributors": [
      "your-email@domain.com"
    ]
  },

  "acls": [
    // Allow CI runner to reach server port 22 (SSH)
    {
      "action": "accept",
      "src": ["tag:ci"],
      "dst": ["tag:server:22"]
    },

    // Allow contributors to reach web preview ports (HTTP 80, Traefik 8080)
    {
      "action": "accept",
      "src": ["group:contributors"],
      "dst": ["tag:server:80,8080"]
    },

    // Allow contributors to reach SSH on server
    {
      "action": "accept",
      "src": ["group:contributors"],
      "dst": ["tag:server:22"]
    }
  ],

  "ssh": [
    // 1. CI can SSH as 'root' with zero prompts
    {
      "action": "accept",
      "src": ["tag:ci"],
      "dst": ["tag:server"],
      "users": ["root"]
    },

    // 2. Contributors can SSH as unprivileged 'devuser'
    {
      "action": "accept",
      "src": ["group:contributors"],
      "dst": ["tag:server"],
      "users": ["devuser"]
    }
  ]
}
```

---

## 3. GitHub Actions Secrets Setup

In your GitHub repository, navigate to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions** and add only these two secrets:

| Secret Name | How to Get It |
| :--- | :--- |
| `TS_OAUTH_CLIENT_ID` | In Tailscale Admin $\rightarrow$ **Settings** $\rightarrow$ **OAuth Clients** $\rightarrow$ Generate Client with scope `Devices:Write` and tag `tag:ci` |
| `TS_OAUTH_SECRET` | The secret key revealed after generating the OAuth Client |

---

## 4. How Developers Use Staging & Previews

### A. Testing API & Swagger UI
1. Ensure Tailscale is running on the developer's laptop.
2. Open the browser:
   - **Staging API**: `http://api.staging-server/docs`
   - **PR #42 Preview**: `http://pr-42.api.staging-server/docs`
   - **Traefik Dashboard**: `http://staging-server:8080`

### B. Viewing Logs (SSH)
Connect via Tailscale SSH as `devuser` (zero keys needed):
```bash
ssh devuser@staging-server
```
Inspect logs for a specific PR preview:
```bash
docker compose -p pr-42 -f /opt/secretshare/worktrees/pr-42/docker-compose.preview.yml logs -f api
```

### C. Database Connection
Connect local GUI tools (TablePlus, DBeaver) directly:
- Host: `staging-server`
- Port: `5432` (staging) or port mapped to the specific service.
