#!/usr/bin/env bash
set -euo pipefail

# One-time SQLite -> PostgreSQL migration helper.
# Usage:
#   DATABASE_URL=postgresql://... POSTGRES_DB=... POSTGRES_USER=... POSTGRES_PASSWORD=... \
#   ./scripts/manual_migrate_to_postgres.sh docker-compose.prod.yml
#
# Optional env:
#   APP_SERVICE=app
#   SQLITE_PATH_IN_CONTAINER=/appdata/database.db
#   SQLITE_MIGRATION_MARK_KEY=sqlite_to_postgres_migrated_v1

COMPOSE_FILE="${1:-docker-compose.prod.yml}"
APP_SERVICE="${APP_SERVICE:-app}"
MARK_KEY="${SQLITE_MIGRATION_MARK_KEY:-sqlite_to_postgres_migrated_v1}"
SQLITE_PATH_IN_CONTAINER="${SQLITE_PATH_IN_CONTAINER:-}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required."
  exit 1
fi

echo "Validating compose environment..."
docker compose -f "${COMPOSE_FILE}" config >/dev/null

echo "Ensuring PostgreSQL service is running..."
docker compose -f "${COMPOSE_FILE}" up -d postgres

if [[ -z "${SQLITE_PATH_IN_CONTAINER}" ]]; then
  for candidate in /appdata/database.db /appdata/data/database.db; do
    if docker compose -f "${COMPOSE_FILE}" run --rm --no-deps "${APP_SERVICE}" sh -lc "[ -f '${candidate}' ]"; then
      SQLITE_PATH_IN_CONTAINER="${candidate}"
      break
    fi
  done
fi

if [[ -z "${SQLITE_PATH_IN_CONTAINER}" ]]; then
  echo "Could not find SQLite file in container."
  echo "Set SQLITE_PATH_IN_CONTAINER explicitly, example:"
  echo "  SQLITE_PATH_IN_CONTAINER=/appdata/database.db ./scripts/manual_migrate_to_postgres.sh ${COMPOSE_FILE}"
  exit 1
fi

echo "Using SQLite source: ${SQLITE_PATH_IN_CONTAINER}"

echo "Running migration..."
docker compose -f "${COMPOSE_FILE}" run --rm --no-deps \
  -v "$(pwd)/scripts:/scripts:ro" \
  "${APP_SERVICE}" \
  python /scripts/migrate_sqlite_to_postgres.py \
    --sqlite-path "${SQLITE_PATH_IN_CONTAINER}" \
    --postgres-url "${DATABASE_URL}" \
    --skip-if-marked \
    --mark-key "${MARK_KEY}"

echo "Running verification..."
docker compose -f "${COMPOSE_FILE}" run --rm --no-deps \
  -v "$(pwd)/scripts:/scripts:ro" \
  "${APP_SERVICE}" \
  python /scripts/verify_postgres_migration.py \
    --sqlite-path "${SQLITE_PATH_IN_CONTAINER}" \
    --postgres-url "${DATABASE_URL}" \
    --require-marker-if-sqlite \
    --mark-key "${MARK_KEY}" \
    --count-mode ge

echo
echo "Migration completed successfully."
echo "Restart services with:"
echo "  docker compose -f ${COMPOSE_FILE} up -d postgres ftp sftp app"
