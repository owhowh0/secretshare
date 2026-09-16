#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

echo "=== OAuth Live Integration Test Suite ==="

# Load .env if present
if [ -f .env ]; then
  echo "Loading configuration from .env..."
  set -a
  source .env
  set +a
fi

# Detect python executable (.venv or system)
PYTHON_BIN="python"
if [ -f "${ROOT_DIR}/.venv/bin/python" ]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
fi

TRAEFIK_PORT="${TRAEFIK_WEB_PORT:-80}"

# If KEYCLOAK_URL uses docker-internal hostname (e.g. http://keycloak:8080/...), map to localhost via Traefik
if [[ "${KEYCLOAK_URL:-}" =~ ://keycloak(:[0-9]+)?(/|$) ]]; then
  export KEYCLOAK_URL="http://127.0.0.1:${TRAEFIK_PORT}${KEYCLOAK_PATH:-/keycloak}"
else
  export KEYCLOAK_URL="${KEYCLOAK_URL:-http://127.0.0.1:${TRAEFIK_PORT}/keycloak}"
fi

export API_BASE_URL="${API_BASE_URL:-}"
export KEYCLOAK_REALM="${KEYCLOAK_REALM:-secretshare}"
export KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-secretshare-api}"
export TEST_USER_USERNAME="${TEST_USER_USERNAME:-testuser}"
export TEST_USER_PASSWORD="${TEST_USER_PASSWORD:-testpassword123}"
export TEST_USER_EMAIL="${TEST_USER_EMAIL:-test@example.com}"
export REQUIRE_KEYCLOAK=1

echo "Target Keycloak: ${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}"
if [ -n "${API_BASE_URL}" ]; then
  echo "Target API:      ${API_BASE_URL} (live HTTP)"
else
  echo "Target API:      In-process ASGI application"
fi

MAX_ATTEMPTS=15
ATTEMPT=1
until curl -s -f -o /dev/null "${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}" || [ $ATTEMPT -ge $MAX_ATTEMPTS ]; do
  echo "Waiting for Keycloak... (attempt ${ATTEMPT}/${MAX_ATTEMPTS})"
  sleep 3
  ATTEMPT=$((ATTEMPT + 1))
done

if ! curl -s -f -o /dev/null "${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}"; then
  echo "Error: Keycloak is not responding at ${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}"
  echo "Tip: Run 'docker compose up -d db keycloak' first."
  exit 1
fi

echo "Keycloak is online! Running live integration tests..."
"${PYTHON_BIN}" -m pytest -v -m integration api/tests/test_oauth_integration.py
echo "=== All OAuth live integration tests passed! ==="
