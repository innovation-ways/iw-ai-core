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

# Signal the app container that the DB is restored and ready for migrations.
# The app container's bootstrap command waits for /workspace/.iw-seed-done
# before running `alembic upgrade head`, which avoids the race where alembic
# would run against a pg_dumped schema that `--clean --if-exists` then drops.
#
# The previous design did `docker exec <app-container> ... uv run alembic`
# from this script. It broke F-00080 (iwcore-164) because the app container
# exited early — `pip install --user` couldn't write /app/.local since /app
# is auto-created root-owned by the /app/.claude bind-mount, leaving the
# runtime user with no writable HOME — and `docker exec` hit a dead
# container with the cryptic "container is not running" error. The seed's
# wait-loop only checked `uv --version`, never `docker inspect Running`.
#
# `cwd` here is the worktree path (the daemon sets subprocess.cwd), which
# is mounted into the app container as /workspace, so the file written here
# is the same one the app container polls.
echo "[seed] writing .iw-seed-done sentinel for the app container ..." >&2
touch .iw-seed-done

echo "[seed] done" >&2
