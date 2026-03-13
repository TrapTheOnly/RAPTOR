#!/usr/bin/env bash
set -euo pipefail

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

docker compose -f docker-compose.dev.yml down -v --remove-orphans
docker compose -f docker-compose.dev.yml up -d --build postgres ftp sftp app mcp

docker cp backend/appdata/shared/example.com_A_Records raptor-sftp-dev:/chroot/upload/example.com_A_Records
(
  [ -f backend/appdata/shared/example1.com_A_Records ] \
    && docker cp backend/appdata/shared/example1.com_A_Records raptor-sftp-dev:/chroot/upload/example1.com_A_Records \
    || (
      sed 's/example.com/example1.com/g' backend/appdata/shared/example.com_A_Records \
      | docker exec -i raptor-sftp-dev sh -c 'cat > /chroot/upload/example1.com_A_Records'
    )
)
docker exec raptor-sftp-dev sh -c 'chown sftpuser:sftpusers /chroot/upload/example.com_A_Records /chroot/upload/example1.com_A_Records && chmod 644 /chroot/upload/example.com_A_Records /chroot/upload/example1.com_A_Records'
