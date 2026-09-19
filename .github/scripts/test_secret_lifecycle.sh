#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1}"
BASE_URL="${BASE_URL%/}"
TOKEN_ARG="${2:-}"

echo "=== Testing Secret Lifecycle at ${BASE_URL}/api/secrets ==="

# Determine or acquire access token
ACCESS_TOKEN=""
if [ -n "${TOKEN_ARG}" ]; then
  if [ -f "${TOKEN_ARG}" ]; then
    ACCESS_TOKEN=$(cat "${TOKEN_ARG}")
  else
    ACCESS_TOKEN="${TOKEN_ARG}"
  fi
fi

if [ -z "${ACCESS_TOKEN}" ]; then
  REALM="${KEYCLOAK_REALM:-secretshare}"
  CLIENT_ID="${KEYCLOAK_CLIENT_ID:-secretshare-api}"
  TEST_USER="${TEST_USER_USERNAME:-testuser}"
  TEST_PASS="${TEST_USER_PASSWORD:-testpassword123}"
  echo "Acquiring access token for authenticated secret test..."
  KC_TOKEN_RESPONSE=$(curl -s -f -m 10 -X POST "${BASE_URL}/keycloak/realms/${REALM}/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=${CLIENT_ID}&grant_type=password&username=${TEST_USER}&password=${TEST_PASS}&scope=openid" || {
      echo "Error: Failed to obtain token from Keycloak for secret testing"
      exit 1
    })
  ACCESS_TOKEN=$(echo "$KC_TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
fi

echo "--- 1. Testing Authenticated Secret Lifecycle ---"
AUTH_PAYLOAD_ID=$(curl -s -f -m 10 -X POST "${BASE_URL}/api/secrets" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{"ciphertext": "authenticated-e2e-smoke-test"}' | grep -o '"payload_id":"[^"]*' | cut -d'"' -f4)

if [ -z "${AUTH_PAYLOAD_ID}" ]; then
  echo "Error: Failed to create authenticated secret"
  exit 1
fi
echo "-> Created authenticated secret: ${AUTH_PAYLOAD_ID}"

AUTH_RETRIEVED=$(curl -s -f -m 10 -X POST "${BASE_URL}/api/secrets/reveal" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d "{\"payload_id\": \"${AUTH_PAYLOAD_ID}\"}" | grep -o '"ciphertext":"[^"]*' | cut -d'"' -f4)

if [ "${AUTH_RETRIEVED}" != "authenticated-e2e-smoke-test" ]; then
  echo "Error: Retrieved authenticated secret does not match expected payload (got: ${AUTH_RETRIEVED})"
  exit 1
fi
echo "-> Successfully retrieved authenticated secret"

AUTH_BURN_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/api/secrets/reveal" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d "{\"payload_id\": \"${AUTH_PAYLOAD_ID}\"}")

[ "${AUTH_BURN_CODE}" = "404" ] || {
  echo "Error: Expected 404 on second retrieval (burn), got ${AUTH_BURN_CODE}"
  exit 1
}
echo "-> Authenticated secret burned successfully (404 on second reveal)"

echo "--- 2. Testing Anonymous Secret Lifecycle ---"
PAYLOAD_ID=$(curl -s -f -m 10 -X POST "${BASE_URL}/api/secrets" \
  -H "Content-Type: application/json" \
  -d '{"ciphertext": "anonymous-e2e-smoke-test"}' | grep -o '"payload_id":"[^"]*' | cut -d'"' -f4)

if [ -z "${PAYLOAD_ID}" ]; then
  echo "Error: Failed to create anonymous secret"
  exit 1
fi
echo "-> Created anonymous secret: ${PAYLOAD_ID}"

RETRIEVED=$(curl -s -f -m 10 -X POST "${BASE_URL}/api/secrets/reveal" \
  -H "Content-Type: application/json" \
  -d "{\"payload_id\": \"${PAYLOAD_ID}\"}" | grep -o '"ciphertext":"[^"]*' | cut -d'"' -f4)

if [ "${RETRIEVED}" != "anonymous-e2e-smoke-test" ]; then
  echo "Error: Retrieved secret does not match expected payload (got: ${RETRIEVED})"
  exit 1
fi
echo "-> Successfully retrieved anonymous secret"

BURN_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/api/secrets/reveal" \
  -H "Content-Type: application/json" \
  -d "{\"payload_id\": \"${PAYLOAD_ID}\"}")

[ "${BURN_CODE}" = "404" ] || {
  echo "Error: Expected 404 on second retrieval (burn), got ${BURN_CODE}"
  exit 1
}
echo "-> Anonymous secret burned successfully (404 on second reveal)"

echo "--- 3. Testing Custom TTL & Validation ---"
TTL_RESPONSE=$(curl -s -f -m 10 -X POST "${BASE_URL}/api/secrets"   -H "Content-Type: application/json"   -d '{"ciphertext": "ttl-e2e-smoke-test", "ttl_seconds": 3600}')
echo "${TTL_RESPONSE}" | grep -q '"ttl_seconds":3600' || {
  echo "Error: custom ttl_seconds not honored: ${TTL_RESPONSE}"
  exit 1
}
echo "${TTL_RESPONSE}" | grep -q '"expires_at":' || {
  echo "Error: expires_at missing from create response: ${TTL_RESPONSE}"
  exit 1
}
echo "-> Custom TTL accepted (3600s) with expires_at"

for BAD_TTL in 10 86401; do
  BAD_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/api/secrets"     -H "Content-Type: application/json"     -d "{\"ciphertext\": \"ttl-e2e-smoke-test\", \"ttl_seconds\": ${BAD_TTL}}")
  [ "${BAD_CODE}" = "422" ] || {
    echo "Error: Expected 422 for ttl_seconds=${BAD_TTL}, got ${BAD_CODE}"
    exit 1
  }
done
echo "-> Out-of-bounds TTL rejected with 422"

echo "=== All Secret Lifecycle tests passed! ==="
