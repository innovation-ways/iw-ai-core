#!/usr/bin/env bash
# F-00062 — iw-ai-core per-worktree DB seed
# Runs after `docker compose up` succeeds for an iw-ai-core worktree.
# pg_dump from the global orch DB on 5433 -> psql restore into the
# per-worktree DB.
#
# The daemon loads the worktree's .env into this script's environment.
# Required env vars:
#   IW_CORE_ORCH_DB_HOST/PORT/NAME/USER/PASSWORD  — global source
#   IW_CORE_DB_PORT                                — per-worktree dest port
#   (other IW_CORE_DB_* are already set)

set -euo pipefail

SRC_URL="postgresql://${IW_CORE_ORCH_DB_USER}:${IW_CORE_ORCH_DB_PASSWORD}@${IW_CORE_ORCH_DB_HOST}:${IW_CORE_ORCH_DB_PORT}/${IW_CORE_ORCH_DB_NAME}"
DST_URL="postgresql://${IW_CORE_DB_USER}:${IW_CORE_DB_PASSWORD}@localhost:${IW_CORE_DB_PORT}/${IW_CORE_DB_NAME}"

echo "[seed] dumping from global orch DB and restoring into per-worktree DB" >&2

# Stream dump → restore. --no-owner / --no-acl avoid role-mismatch errors.
pg_dump --no-owner --no-acl --clean --if-exists "$SRC_URL" \
  | psql --quiet --set ON_ERROR_STOP=1 "$DST_URL"

echo "[seed] done" >&2