#!/usr/bin/env bash
set -euo pipefail

CLEAN=false
NO_SCANNER=false
BUILD=false
for arg in "$@"; do
  case "$arg" in
    --clean|-v)      CLEAN=true ;;
    --no-scanner|-n) NO_SCANNER=true ;;
    --build|-b)      BUILD=true ;;
  esac
done

export POSTGRES_DB="${POSTGRES_DB:-raptor}"
export POSTGRES_USER="${POSTGRES_USER:-raptor}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-raptor}"
export DATABASE_URL="${DATABASE_URL:-postgresql://raptor:raptor@postgres:5432/raptor}"
export DATA_PATH="${DATA_PATH:-/appdata/data}"
export BACKUP_FOLDER="${BACKUP_FOLDER:-/appdata/backups}"
export SHARED_PATH="${SHARED_PATH:-/usr/app/src/shared}"
export APP_PORT="${APP_PORT:-5000}"
export MCP_SERVER_TOKEN="${MCP_SERVER_TOKEN:-raptor-mcp-dev-token}"
export RAPTOR_SERVICE_API_KEY="${RAPTOR_SERVICE_API_KEY:-raptor-mcp-dev-service-key}"
export RAPTOR_API_BASE_URL="${RAPTOR_API_BASE_URL:-http://app:5000}"
export MCP_PORT="${MCP_PORT:-8081}"
export RAPTOR_API_TIMEOUT_SECONDS="${RAPTOR_API_TIMEOUT_SECONDS:-30}"
export SCANNER_INTERNAL_TOKEN="${SCANNER_INTERNAL_TOKEN:-raptor-scanner-dev-token}"

if [[ "$NO_SCANNER" == false ]] && [[ -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]]; then
  echo "WARNING: AWS_BEARER_TOKEN_BEDROCK is not set — scanner container will fail to start." >&2
  echo "WARNING: Set it in your shell or re-run with --no-scanner to skip scanner + kali." >&2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE="docker-compose.dev.yml"

cd "$ROOT"

DOWN_ARGS=("-f" "$COMPOSE" "down" "--remove-orphans")
if [[ "$CLEAN" == true ]]; then DOWN_ARGS+=("-v"); fi
docker compose "${DOWN_ARGS[@]}"

SERVICES=("postgres" "ftp" "sftp" "app" "mcp")
if [[ "$NO_SCANNER" == false ]]; then
  SERVICES+=("kali" "scanner")
fi

UP_ARGS=("-f" "$COMPOSE" "up" "-d")
if [[ "$BUILD" == true ]]; then UP_ARGS+=("--build"); fi
UP_ARGS+=("${SERVICES[@]}")
docker compose "${UP_ARGS[@]}"

SHARED_SRC="$ROOT/backend/appdata/shared"
PRIMARY_ZONE="$SHARED_SRC/example.com_A_Records"
SECONDARY_ZONE="$SHARED_SRC/example1.com_A_Records"

if [[ -f "$PRIMARY_ZONE" ]]; then
  docker cp "$PRIMARY_ZONE" "raptor-sftp-dev:/chroot/upload/example.com_A_Records"

  if [[ -f "$SECONDARY_ZONE" ]]; then
    docker cp "$SECONDARY_ZONE" "raptor-sftp-dev:/chroot/upload/example1.com_A_Records"
  else
    sed 's/example\.com/example1.com/g' "$PRIMARY_ZONE" \
      | docker exec -i raptor-sftp-dev sh -c 'cat > /chroot/upload/example1.com_A_Records'
  fi

  docker exec raptor-sftp-dev sh -c \
    'chown sftpuser:sftpusers /chroot/upload/example.com_A_Records /chroot/upload/example1.com_A_Records && chmod 644 /chroot/upload/example.com_A_Records /chroot/upload/example1.com_A_Records'
else
  echo "WARNING: Zone file not found at $PRIMARY_ZONE — skipping SFTP seed." >&2
fi

echo ""
echo "RAPTOR dev stack is up."
echo "  App:     http://localhost:1337"
echo "  MCP:     http://localhost:${MCP_PORT}"
if [[ "$NO_SCANNER" == false ]]; then
  echo "  Scanner: http://localhost:8082  (internal)"
fi
