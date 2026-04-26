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

echo "[seed] done" >&2
