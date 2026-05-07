#!/usr/bin/env bash
# F-00062 — iw-ai-core per-worktree DB seed
#
# Runs after `docker compose up` succeeds for an iw-ai-core worktree.
# Streams pg_dump from the global orch DB container into the per-worktree
# DB container via `docker exec`, so no host install of postgresql-client
# is required.
#
# The daemon loads the worktree's .env into this script's environment and
# additionally injects:
#   IW_CORE_BATCH_ITEM_ID         — batch_item PK (e.g. "98")
#   IW_CORE_COMPOSE_PROJECT_NAME  — compose project (e.g. "iwcore-98")
#
# Required env vars (set by daemon/.env):
#   IW_CORE_ORCH_DB_USER / NAME    — global source DB credentials
#   IW_CORE_DB_USER     / NAME     — per-worktree dest DB credentials

set -euo pipefail

ORCH_CONTAINER="${IW_CORE_ORCH_DB_CONTAINER:-postgres}"
WORKTREE_DB_CONTAINER="${IW_CORE_COMPOSE_PROJECT_NAME}-db-1"
WORKTREE_APP_CONTAINER="${IW_CORE_COMPOSE_PROJECT_NAME}-app-1"

echo "[seed] dump from ${ORCH_CONTAINER} -> restore into ${WORKTREE_DB_CONTAINER}" >&2

docker exec \
  -e PGPASSWORD="${IW_CORE_ORCH_DB_PASSWORD}" \
  "${ORCH_CONTAINER}" \
  pg_dump --no-owner --no-acl --clean --if-exists \
    -U "${IW_CORE_ORCH_DB_USER}" \
    -d "${IW_CORE_ORCH_DB_NAME}" \
| docker exec -i \
  -e PGPASSWORD="${IW_CORE_DB_PASSWORD}" \
  "${WORKTREE_DB_CONTAINER}" \
  psql --quiet --set ON_ERROR_STOP=1 \
    -U "${IW_CORE_DB_USER}" \
    -d "${IW_CORE_DB_NAME}"

# After pg_dump restores production schema, apply any worktree-local migrations
# so the per-worktree DB matches the worktree's models.py. This closes the gap
# observed in F-00079 where S19 hit `column work_items.diff_text does not exist`
# because S01's new migration was on disk but never applied to the E2E DB.
echo "[seed] applying worktree migrations via ${WORKTREE_APP_CONTAINER}..." >&2
docker exec "${WORKTREE_APP_CONTAINER}" bash -lc '
  set -euo pipefail
  export HOME=/app PATH="/tmp/.local/bin:$PATH" UV_PROJECT_ENVIRONMENT=/tmp/.venv
  cd /workspace
  # Wait until the app container has finished its initial `uv sync` so
  # `uv run alembic` resolves. The compose command runs uv sync before
  # uvicorn, so this loop is bounded in practice.
  for _ in $(seq 1 60); do
    if uv --version >/dev/null 2>&1 && [ -d "${UV_PROJECT_ENVIRONMENT}" ]; then
      break
    fi
    sleep 2
  done
  uv run alembic upgrade head
'

echo "[seed] done" >&2
