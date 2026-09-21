#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1}"
BASE_URL="${BASE_URL%/}"

echo "=== Testing API Health, Swagger Docs & OpenAPI Schema at ${BASE_URL}/api ==="

echo "--- Testing /api/health ---"
HEALTH_RESPONSE=$(curl -s -k -f -m 5 "${BASE_URL}/api/health" || {
  echo "Error: /api/health failed"
  curl -v -k -m 5 "${BASE_URL}/api/health" || true
  exit 1
})
echo "$HEALTH_RESPONSE" | grep -q '"status":"ok"' || {
  echo "Error: /api/health returned unexpected response: ${HEALTH_RESPONSE}"
  exit 1
}
echo "-> /api/health status is ok"

echo "--- Testing /api/docs ---"
curl -s -k -f -m 5 "${BASE_URL}/api/docs" >/dev/null || {
  echo "Error: /api/docs failed"
  curl -v -k -m 5 "${BASE_URL}/api/docs" || true
  exit 1
}
echo "-> /api/docs responded with 200 OK"

echo "--- Testing /api/openapi.json ---"
OPENAPI_JSON=$(curl -s -k -f -m 5 "${BASE_URL}/api/openapi.json" || {
  echo "Error: /api/openapi.json failed to fetch"
  exit 1
})
echo "$OPENAPI_JSON" | grep -q '"/health"' || {
  echo "Error: /api/openapi.json invalid: missing /health path"
  echo "$OPENAPI_JSON"
  exit 1
}
echo "-> /api/openapi.json schema verified"

echo "=== All API documentation and health tests passed! ==="
