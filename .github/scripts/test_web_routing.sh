#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1}"
BASE_URL="${BASE_URL%/}" # normalize by stripping trailing slash
CHECK_REDIRECT="${2:-true}"

echo "=== Testing Web UI & Static Assets at ${BASE_URL} ==="

if [ "${CHECK_REDIRECT}" = "true" ] && [[ "${BASE_URL}" =~ /pr-[0-9]+$ ]]; then
  echo "--- Testing trailing-slash redirect on ${BASE_URL} ---"
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}" || echo "CURL_ERR_$?")
  echo "-> Redirect status code: ${HTTP_CODE}"
  if [ "${HTTP_CODE}" != "301" ] && [ "${HTTP_CODE}" != "308" ] && [ "${HTTP_CODE}" != "200" ]; then
    echo "Error: Unexpected HTTP code ${HTTP_CODE} for ${BASE_URL}"
    exit 1
  fi
fi

echo "--- Testing Frontend HTML Document ---"
HTML_OUTPUT=$(curl -s -f -L -m 5 "${BASE_URL}/" || {
  echo "Error: curl failed to fetch ${BASE_URL}/"
  curl -v -m 10 "${BASE_URL}/" || true
  exit 1
})

echo "$HTML_OUTPUT" | grep -q 'SecretShare' || { echo "Error: SecretShare title missing in HTML"; echo "$HTML_OUTPUT"; exit 1; }
if echo "$HTML_OUTPUT" | grep -q 'id="login-btn"'; then
  echo "-> Found id=\"login-btn\""
fi
if echo "$HTML_OUTPUT" | grep -q 'id="create-btn"'; then
  echo "-> Found id=\"create-btn\""
fi

echo "--- Testing Next.js Static Asset Resolution ---"
NEXT_ASSET_PATH=$(echo "$HTML_OUTPUT" | grep -oE "(/pr-[0-9]+)?/_next/static/[^\"]+\\.js" | head -n1 || true)
[ -n "$NEXT_ASSET_PATH" ] || { echo "Error: Next.js static asset reference missing in HTML"; echo "$HTML_OUTPUT"; exit 1; }
echo "-> Found Next.js static asset: ${NEXT_ASSET_PATH}"

ORIGIN=$(echo "${BASE_URL}" | grep -oE "^https?://[^/]+")
curl -s -f -m 5 "${ORIGIN}${NEXT_ASSET_PATH}" >/dev/null || {
  echo "Error: Failed to fetch Next.js static asset ${ORIGIN}${NEXT_ASSET_PATH}"
  curl -v -m 5 "${ORIGIN}${NEXT_ASSET_PATH}" || true
  exit 1
}

echo "=== All Web UI and routing tests passed! ==="
