#!/usr/bin/env bash
# Bring up Postgres + the FastAPI server locally with auth bypassed.
#
# Usage: ./scripts/dev/up.sh
# Stops with Ctrl-C. Postgres keeps running in the background; tear it down
# with `./scripts/dev/down.sh`.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

# shellcheck disable=SC1091
source scripts/dev/.env

echo ">>> starting postgres"
docker compose -f scripts/dev/docker-compose.yml up -d

echo ">>> waiting for postgres healthy"
for _ in {1..30}; do
  status=$(docker inspect -f '{{.State.Health.Status}}' hackathon-local-pg 2>/dev/null || echo "starting")
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  sleep 1
done
if [[ "$status" != "healthy" ]]; then
  echo "!!! postgres did not become healthy"
  exit 1
fi

echo ">>> starting uvicorn on http://localhost:8000"
echo ">>> LOCAL_DEV=1 — every request authenticates as user=$LOCAL_DEV_SUB team=$LOCAL_DEV_TEAM"
echo ">>> health: curl http://localhost:8000/health"
echo ">>> papers: curl http://localhost:8000/api/papers"

# The cloud API has its own dependency set (see infra/docker/api/requirements.txt)
# that doesn't overlap with the team CLI's pyproject deps. Pull them in just
# for this process so we don't pollute the project lockfile.
exec uv run \
  --with "psycopg[binary]>=3.2" \
  --with "sqlalchemy>=2.0" \
  --with "python-jose[cryptography]>=3.3" \
  --with "httpx>=0.27" \
  uvicorn cloud_api.main:app --host 127.0.0.1 --port 8000 --reload
