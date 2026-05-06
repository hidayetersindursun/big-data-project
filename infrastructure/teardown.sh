#!/usr/bin/env bash
# ============================================================================
# Turkey Food Supply Chain — tear down local stack
#
# Usage:
#   ./teardown.sh           # stop containers, keep volumes (fast restart later)
#   ./teardown.sh --wipe    # stop AND delete volumes (fresh state next time)
# ============================================================================

set -euo pipefail

cd "$(dirname "$0")"

if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
else
    DC="docker-compose"
fi

SUDO=""
docker ps >/dev/null 2>&1 || SUDO="sudo"

if [[ "${1:-}" == "--wipe" ]]; then
    echo "[teardown] stopping stack AND deleting volumes..."
    $SUDO $DC down -v --remove-orphans
else
    echo "[teardown] stopping stack (volumes preserved)..."
    $SUDO $DC down --remove-orphans
fi

echo "[teardown] done"
