#!/bin/bash
set -e

KC_DB="${KEYCLOAK_DB:-keycloak}"

echo "=== Initializing Keycloak database: ${KC_DB} ==="

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT format('CREATE DATABASE %I', '${KC_DB}')
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${KC_DB}')\gexec
    GRANT ALL PRIVILEGES ON DATABASE "${KC_DB}" TO "${POSTGRES_USER}";
EOSQL
