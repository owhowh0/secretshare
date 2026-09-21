#!/bin/sh
# Generates a self-signed CA and issues server certificates for PostgreSQL and
# Redis. Idempotent: skips generation if the CA certificate already exists.
set -e

CERTS=/certs

if [ -f "$CERTS/ca.crt" ]; then
    echo "tls: certificates already present, skipping generation."
    exit 0
fi

echo "tls: generating internal CA and service certificates..."

# ── CA ──────────────────────────────────────────────────────────────────────
openssl genrsa -out "$CERTS/ca.key" 4096
openssl req -x509 -new -nodes -key "$CERTS/ca.key" -sha256 -days 3650 \
    -subj "/CN=secretshare-internal-ca" \
    -out "$CERTS/ca.crt"

# ── PostgreSQL ───────────────────────────────────────────────────────────────
openssl genrsa -out "$CERTS/postgres.key" 4096
openssl req -new -key "$CERTS/postgres.key" -subj "/CN=db" \
    -out "$CERTS/postgres.csr"
openssl x509 -req -in "$CERTS/postgres.csr" -sha256 -days 3650 \
    -CA "$CERTS/ca.crt" -CAkey "$CERTS/ca.key" -CAcreateserial \
    -out "$CERTS/postgres.crt"
rm "$CERTS/postgres.csr"

# ── Redis ────────────────────────────────────────────────────────────────────
openssl genrsa -out "$CERTS/redis.key" 4096
openssl req -new -key "$CERTS/redis.key" -subj "/CN=redis" \
    -out "$CERTS/redis.csr"
openssl x509 -req -in "$CERTS/redis.csr" -sha256 -days 3650 \
    -CA "$CERTS/ca.crt" -CAkey "$CERTS/ca.key" -CAcreateserial \
    -out "$CERTS/redis.crt"
rm "$CERTS/redis.csr"

# ── Permissions ──────────────────────────────────────────────────────────────
# Keys are root-owned 600. Each service entrypoint copies its own key and
# re-owns it to the service user (postgres UID 70, redis UID 999 in alpine).
chmod 600 "$CERTS"/*.key
chmod 644 "$CERTS"/*.crt

echo "tls: done."
