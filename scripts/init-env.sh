#!/bin/sh
# Creates .env from .env.example, replacing every secret placeholder with a
# fresh random value. The compose files have no fallback secrets, so this (or
# an .env written by hand) is required before the first `docker compose up`.
#
#   sh scripts/init-env.sh
#
# Refuses to overwrite an existing .env. Never prints the generated values.
set -eu

cd "$(dirname "$0")/.."

if [ -e .env ]; then
  echo ".env already exists; not overwriting it." >&2
  exit 1
fi
command -v openssl >/dev/null 2>&1 || { echo "openssl is required." >&2; exit 1; }

PLACEHOLDER=replace_with_a_secure_random_password
postgres_password=""

umask 077  # .env holds secrets: readable by the owner only
tmp=$(mktemp .env.XXXXXX)
trap 'rm -f "$tmp"' EXIT

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    POSTGRES_PASSWORD=*)
      postgres_password=$(openssl rand -hex 24)
      line="POSTGRES_PASSWORD=$postgres_password"
      ;;
    *"$PLACEHOLDER"*)
      line=$(printf '%s\n' "$line" | sed "s/$PLACEHOLDER/$(openssl rand -hex 32)/")
      ;;
    *"<password>"*)
      # Host-side DATABASE_URL / TEST_DATABASE_URL use the same database user.
      line=$(printf '%s\n' "$line" | sed "s/<password>/$postgres_password/")
      ;;
  esac
  printf '%s\n' "$line"
done < .env.example > "$tmp"

mv "$tmp" .env
trap - EXIT

# Ensure external network required by compose exists
if command -v docker >/dev/null 2>&1; then
  docker network create traefik-net 2>/dev/null || true
fi

echo "Created .env with random secrets (mode 600)."
