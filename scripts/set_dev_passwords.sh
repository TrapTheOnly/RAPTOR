#!/usr/bin/env bash
# Copy the password helper into the running app container and execute it.
# The scripts/ tree is not baked into the image.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${RAPTOR_APP_CONTAINER:-raptor-dev}"
SRC="$ROOT/scripts/set_dev_passwords.py"
DEST="/tmp/set_dev_passwords.py"

if [[ ! -f "$SRC" ]]; then
  echo "Missing $SRC" >&2
  exit 1
fi

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "Container $CONTAINER is not running." >&2
  echo "Start the stack first: ./scripts/docker_runner.sh --no-scanner --build" >&2
  exit 1
fi

echo "Copying helper into $CONTAINER ..."
docker cp "$SRC" "$CONTAINER:$DEST"
docker exec \
  -e PYTHONPATH=/usr/app/src/backend \
  "$CONTAINER" \
  python "$DEST" "$@"
