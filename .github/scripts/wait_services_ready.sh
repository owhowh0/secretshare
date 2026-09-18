#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1}"
COMPOSE_PROJECT="${2:-}"
COMPOSE_FILE="${3:-docker-compose.preview.yml}"
MAX_ATTEMPTS="${4:-30}"

echo "=== Waiting for services to become ready at ${BASE_URL} ==="
ATTEMPTS=0
READY=0
while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
  ATTEMPTS=$((ATTEMPTS + 1))
  WEB_CODE=$(curl -s -k -o /dev/null -w "%{http_code}" -m 5 "${BASE_URL}/" || echo "CURL_ERR_$?")
  API_CODE=$(curl -s -k -o /dev/null -w "%{http_code}" -m 5 "${BASE_URL}/api/health" || echo "CURL_ERR_$?")
  KC_CODE=$(curl -s -k -o /dev/null -w "%{http_code}" -m 5 "${BASE_URL}/keycloak/realms/secretshare" || echo "CURL_ERR_$?")
  echo "[$(date +'%T')] [Attempt ${ATTEMPTS}/${MAX_ATTEMPTS}] Web: ${WEB_CODE} | API: ${API_CODE} | Keycloak: ${KC_CODE}"
  if [ "${WEB_CODE}" = "200" ] && [ "${API_CODE}" = "200" ] && [ "${KC_CODE}" = "200" ]; then
    echo "=== All services responded with 200 OK! ==="
    READY=1
    break
  fi
  sleep 2
done

if [ "$READY" -ne 1 ]; then
  echo "=== Readiness verification timed out after ${MAX_ATTEMPTS} attempts! ==="
  echo "=== Diagnostic curl to Web: ==="
  curl -v -L -m 10 "${BASE_URL}/" || true
  echo "=== Diagnostic curl to API: ==="
  curl -v -m 10 "${BASE_URL}/api/health" || true
  echo "=== Diagnostic curl to Keycloak: ==="
  curl -v -m 10 "${BASE_URL}/keycloak/realms/secretshare" || true
  echo "=== Active Traefik Routers: ==="
  curl -s http://127.0.0.1:8080/api/http/routers || true
  if [ -n "${COMPOSE_PROJECT}" ]; then
    echo "=== Container Status: ==="
    docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" ps -a || true
    echo "=== WEB CONTAINER LOGS (last 100 lines): ==="
    docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" logs --tail 100 web || true
    echo "=== API CONTAINER LOGS (last 100 lines): ==="
    docker compose -p "${COMPOSE_PROJECT}" -f "${COMPOSE_FILE}" logs --tail 100 api || true
  fi
  echo "=== TRAEFIK LOGS (last 50 lines): ==="
  docker logs --tail 50 traefik || true
  exit 1
fi
