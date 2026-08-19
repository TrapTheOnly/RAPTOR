#!/usr/bin/env bash
# Copy the demo seeder into the running app container and execute it.
# The scripts/ tree is not baked into the image.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${RAPTOR_APP_CONTAINER:-raptor-dev}"
SRC="$ROOT/scripts/seed_demo_world.py"
DEST="/tmp/seed_demo_world.py"

if [[ ! -f "$SRC" ]]; then
  echo "Missing $SRC" >&2
  exit 1
fi

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "Container $CONTAINER is not running." >&2
  echo "Start the stack first: ./scripts/docker_runner.sh --no-scanner --build" >&2
  exit 1
fi

echo "Copying seeder into $CONTAINER ..."
docker cp "$SRC" "$CONTAINER:$DEST"
echo "Seeding demo world ..."
docker exec \
  -e PYTHONPATH=/usr/app/src/backend \
  "$CONTAINER" \
  python "$DEST" "$@"
