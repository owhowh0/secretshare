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
  KC_TOKEN_RESPONSE=$(curl -s -k -f -m 10 -X POST "${BASE_URL}/keycloak/realms/${REALM}/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=${CLIENT_ID}&grant_type=password&username=${TEST_USER}&password=${TEST_PASS}&scope=openid" || {
      echo "Error: Failed to obtain token from Keycloak for secret testing"
      exit 1
    })
  ACCESS_TOKEN=$(echo "$KC_TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
fi

TEST_USER="${TEST_USER_USERNAME:-testuser}"
AUTH_HEADER="Authorization: Bearer ${ACCESS_TOKEN}"

# A create body addressed to $1 with ciphertext $2 (plus optional extra JSON
# fields in $3). The key material is opaque to the server, so fixed test
# values are enough here.
envelope() {
  printf '{"recipient_id": "%s", "encrypted_keys": [{"device_id": "00000000-0000-0000-0000-000000000001", "platform": "web", "encrypted_aes_key": "ZW5jcnlwdGVkLWtleQ=="}], "iv": "MTIzNDU2Nzg5MDEy", "ciphertext": "%s"%s}' "$1" "$2" "${3:-}"
}

create_secret() {
  curl -s -k -f -m 10 -X POST "${BASE_URL}/api/secrets" \
    -H "Content-Type: application/json" -H "${AUTH_HEADER}" \
    -d "$(envelope "$1" "$2" "${3:-}")" | grep -o '"payload_id":"[^"]*' | cut -d'"' -f4
}

reveal_code() {  # $1 payload id, $2 optional auth header ("" for none)
  if [ -n "${2:-}" ]; then
    curl -s -k -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/api/secrets/reveal" \
      -H "Content-Type: application/json" -H "$2" -d "{\"payload_id\": \"$1\"}"
  else
    curl -s -k -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/api/secrets/reveal" \
      -H "Content-Type: application/json" -d "{\"payload_id\": \"$1\"}"
  fi
}

still_exists() {
  curl -s -k -f -m 10 "${BASE_URL}/api/secrets/$1/exists" | grep -q '"exists":true'
}

echo "--- 1. Testing Recipient Secret Lifecycle ---"
AUTH_PAYLOAD_ID=$(create_secret "${TEST_USER}" "authenticated-e2e-smoke-test")
if [ -z "${AUTH_PAYLOAD_ID}" ]; then
  echo "Error: Failed to create secret for ${TEST_USER}"
  exit 1
fi
echo "-> Created secret for ${TEST_USER}: ${AUTH_PAYLOAD_ID}"

AUTH_RETRIEVED=$(curl -s -k -f -m 10 -X POST "${BASE_URL}/api/secrets/reveal" \
  -H "Content-Type: application/json" -H "${AUTH_HEADER}" \
  -d "{\"payload_id\": \"${AUTH_PAYLOAD_ID}\"}" | grep -o '"ciphertext":"[^"]*' | cut -d'"' -f4)
if [ "${AUTH_RETRIEVED}" != "authenticated-e2e-smoke-test" ]; then
  echo "Error: Retrieved secret does not match expected payload (got: ${AUTH_RETRIEVED})"
  exit 1
fi
echo "-> Recipient retrieved the secret"

AUTH_BURN_CODE=$(reveal_code "${AUTH_PAYLOAD_ID}" "${AUTH_HEADER}")
[ "${AUTH_BURN_CODE}" = "404" ] || {
  echo "Error: Expected 404 on second retrieval (burn), got ${AUTH_BURN_CODE}"
  exit 1
}
echo "-> Secret burned after reveal (404 on second reveal)"

echo "--- 2. Testing Denied Reveals Do Not Burn ---"
OTHER_PAYLOAD_ID=$(create_secret "someone-else-e2e" "not-for-testuser-e2e")
if [ -z "${OTHER_PAYLOAD_ID}" ]; then
  echo "Error: Failed to create secret addressed to another user"
  exit 1
fi

for ATTEMPT in 1 2; do
  WRONG_CODE=$(reveal_code "${OTHER_PAYLOAD_ID}" "${AUTH_HEADER}")
  [ "${WRONG_CODE}" = "403" ] || {
    echo "Error: Expected 403 for wrong recipient (attempt ${ATTEMPT}), got ${WRONG_CODE}"
    exit 1
  }
done
still_exists "${OTHER_PAYLOAD_ID}" || {
  echo "Error: a denied reveal burned the secret (exists=false after 403)"
  exit 1
}
echo "-> Wrong recipient refused with 403 and the secret survived"

ANON_CODE=$(reveal_code "${OTHER_PAYLOAD_ID}" "")
[ "${ANON_CODE}" = "401" ] || [ "${ANON_CODE}" = "403" ] || {
  echo "Error: Expected 401/403 for an unauthenticated reveal, got ${ANON_CODE}"
  exit 1
}
still_exists "${OTHER_PAYLOAD_ID}" || {
  echo "Error: an unauthenticated reveal burned the secret"
  exit 1
}
echo "-> Unauthenticated reveal refused (${ANON_CODE}) and the secret survived"

echo "--- 3. Testing Custom TTL & Validation ---"
TTL_RESPONSE=$(curl -s -k -f -m 10 -X POST "${BASE_URL}/api/secrets" \
  -H "Content-Type: application/json" -H "${AUTH_HEADER}" \
  -d "$(envelope "${TEST_USER}" "ttl-e2e-smoke-test" ', "ttl_seconds": 3600')")
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
  BAD_CODE=$(curl -s -k -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/api/secrets" \
    -H "Content-Type: application/json" -H "${AUTH_HEADER}" \
    -d "$(envelope "${TEST_USER}" "ttl-e2e-smoke-test" ", \"ttl_seconds\": ${BAD_TTL}")")
  [ "${BAD_CODE}" = "422" ] || {
    echo "Error: Expected 422 for ttl_seconds=${BAD_TTL}, got ${BAD_CODE}"
    exit 1
  }
done
echo "-> Out-of-bounds TTL rejected with 422"

echo "=== All Secret Lifecycle tests passed! ==="
