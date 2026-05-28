#!/usr/bin/env bash
# Stop the local Postgres container.
# Add `--volumes` to also wipe the database.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

if [[ "${1:-}" == "--volumes" ]]; then
  docker compose -f scripts/dev/docker-compose.yml down --volumes
else
  docker compose -f scripts/dev/docker-compose.yml down
fi
