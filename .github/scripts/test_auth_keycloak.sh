#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1}"
BASE_URL="${BASE_URL%/}"
REALM="${KEYCLOAK_REALM:-secretshare}"
CLIENT_ID="${KEYCLOAK_CLIENT_ID:-secretshare-api}"
TEST_USER="${TEST_USER_USERNAME:-testuser}"
TEST_PASS="${TEST_USER_PASSWORD:-testpassword123}"
TOKEN_FILE="${2:-}"

echo "=== Testing Authentication & Keycloak Integration at ${BASE_URL} ==="

echo "--- 1. Testing NextAuth Providers Endpoint ---"
AUTH_PROVIDERS=$(curl -s -f -L -m 5 "${BASE_URL}/api/auth/providers" || {
  echo "Error: NextAuth /api/auth/providers failed"
  curl -v -L -m 5 "${BASE_URL}/api/auth/providers" || true
  exit 1
})
echo "$AUTH_PROVIDERS" | grep -q 'keycloak' || {
  echo "Error: Keycloak provider not found in /api/auth/providers: ${AUTH_PROVIDERS}"
  exit 1
}
echo "-> NextAuth keycloak provider endpoint verified"

echo "--- 2. Testing Keycloak OIDC Discovery Endpoint ---"
OIDC_DISCOVERY=$(curl -s -f -m 5 "${BASE_URL}/keycloak/realms/${REALM}/.well-known/openid-configuration" || {
  echo "Error: Keycloak OIDC discovery request failed"
  curl -v -m 5 "${BASE_URL}/keycloak/realms/${REALM}/.well-known/openid-configuration" || true
  exit 1
})
echo "$OIDC_DISCOVERY" | grep -q 'token_endpoint' || {
  echo "Error: OIDC discovery missing token_endpoint: ${OIDC_DISCOVERY}"
  exit 1
}
echo "-> Keycloak OIDC discovery endpoint verified"

echo "--- 3. Testing Keycloak Token Issuance (OAuth Password Grant) ---"
KC_TOKEN_RESPONSE=$(curl -s -f -m 10 -X POST "${BASE_URL}/keycloak/realms/${REALM}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=${CLIENT_ID}&grant_type=password&username=${TEST_USER}&password=${TEST_PASS}&scope=openid" || {
    echo "Error: Keycloak token endpoint POST failed"
    exit 1
  })

ACCESS_TOKEN=$(echo "$KC_TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
if [ -z "${ACCESS_TOKEN}" ]; then
  echo "Error: Failed to obtain access_token from Keycloak: ${KC_TOKEN_RESPONSE}"
  exit 1
fi
echo "-> Successfully acquired Keycloak user access token"

if [ -n "${TOKEN_FILE}" ]; then
  echo -n "${ACCESS_TOKEN}" > "${TOKEN_FILE}"
fi

echo "--- 4. Testing Protected /api/me Endpoint ---"
ME_RESPONSE=$(curl -s -f -m 10 "${BASE_URL}/api/me" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" || {
    echo "Error: /api/me failed with valid token"
    curl -v -m 10 "${BASE_URL}/api/me" -H "Authorization: Bearer ${ACCESS_TOKEN}" || true
    exit 1
  })
echo "$ME_RESPONSE" | grep -q "\"preferred_username\":\"${TEST_USER}\"" || {
  echo "Error: /api/me returned unexpected user profile: ${ME_RESPONSE}"
  exit 1
}
echo "-> Valid token accepted for user ${TEST_USER}"

CODE_NO_AUTH=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/me")
[ "${CODE_NO_AUTH}" = "403" ] || {
  echo "Error: Expected 403 for unauthenticated /api/me, got ${CODE_NO_AUTH}"
  exit 1
}

CODE_BAD_AUTH=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer invalid.token" "${BASE_URL}/api/me")
[ "${CODE_BAD_AUTH}" = "401" ] || {
  echo "Error: Expected 401 for invalid token on /api/me, got ${CODE_BAD_AUTH}"
  exit 1
}
echo "-> Auth guards verified (403 without token, 401 with invalid token)"

echo "=== All Authentication & Keycloak integration tests passed! ==="
