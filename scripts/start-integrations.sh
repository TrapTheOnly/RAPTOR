#!/usr/bin/env bash
# Start local Jira Software + DefectDojo for RAPTOR integration testing.
# Separate from docker-compose.dev.yml. Attaches to raptor_app_network when it exists.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/deploy/integrations/docker-compose.yml"
NETWORK="${RAPTOR_NETWORK:-raptor_app_network}"
TIMEOUT="${INTEGRATIONS_WAIT_TIMEOUT:-1200}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing dependency: $1"
}

require_cmd docker
[[ -f "$COMPOSE_FILE" ]] || fail "Missing $COMPOSE_FILE"

if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
  echo "Creating Docker network $NETWORK (start RAPTOR with ./scripts/docker_runner.sh so the app can reach Jira/Dojo)."
  docker network create "$NETWORK" >/dev/null
fi

echo "Starting Jira (localhost:8090) and DefectDojo (localhost:8088)..."
echo "Jira first boot is slow (often 5–10 minutes). The 3-hour Atlassian timebomb license is applied automatically."
docker compose -f "$COMPOSE_FILE" up -d --build "$@"

wait_exit() {
  local name="$1"
  local deadline=$((SECONDS + TIMEOUT))
  echo "Waiting for $name to finish seeding..."
  while (( SECONDS < deadline )); do
    local status
    status="$(docker inspect -f '{{.State.Status}}|{{.State.ExitCode}}' "$name" 2>/dev/null || true)"
    if [[ "$status" == "exited|0" ]]; then
      echo "$name completed."
      return 0
    fi
    if [[ "$status" == exited|* && "$status" != "exited|0" ]]; then
      echo "$name failed ($status). Last logs:" >&2
      docker logs --tail 80 "$name" >&2 || true
      return 1
    fi
    sleep 8
  done
  echo "$name did not finish within ${TIMEOUT}s. Last logs:" >&2
  docker logs --tail 80 "$name" >&2 || true
  return 1
}

failed=0
wait_exit raptor-dojo-seed || failed=1
wait_exit raptor-jira-seed || failed=1

CREDS="$ROOT/deploy/integrations/generated/credentials.json"
if [[ -f "$CREDS" ]]; then
  echo
  echo "Seed output: $CREDS"
  python3 - <<'PY' "$CREDS" || cat "$CREDS"
import json, sys
data = json.load(open(sys.argv[1]))
jira = data.get("jira") or {}
dojo = data.get("defectdojo") or {}
print("Jira")
print(f"  Browser:  {jira.get('browser_url')}")
print(f"  RAPTOR:   {jira.get('raptor_base_url')}  (fallback {jira.get('docker_url')})")
print(f"  User:     {jira.get('username')} / {jira.get('password')}")
print(f"  Auth:     {jira.get('auth_type_preferred')}")
if jira.get("personal_access_token"):
    print(f"  PAT:      {jira['personal_access_token']}")
print("DefectDojo")
print(f"  Browser:  {dojo.get('browser_url')}")
print(f"  RAPTOR:   {dojo.get('raptor_base_url')}  (fallback {dojo.get('docker_url')})")
print(f"  User:     {dojo.get('username')} / {dojo.get('password')}")
print(f"  API key:  {dojo.get('api_key')}")
PY
fi

if [[ "$failed" -ne 0 ]]; then
  fail "One or more seeders failed. See logs above and deploy/integrations/README.md."
fi

echo
echo "Lab stack is ready. Connect RAPTOR in Settings → Integrations using the URLs above."
echo "See deploy/integrations/README.md for field-mapping steps and the Jira license warning."
