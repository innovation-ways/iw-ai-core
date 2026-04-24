#!/usr/bin/env bash
# Dashboard entrypoint for the E2E stack.
#
# Runs (in order):
#   1. alembic upgrade head  — apply the worktree's migrations to the e2e DB
#   2. scripts/e2e_seed.py   — insert project + architecture-map + modules
#   3. uvicorn dashboard     — serve on 0.0.0.0:9900 (dashboard port inside the container)
#
# Environment variables expected (set by docker-compose.e2e.yml):
#   IW_CORE_DB_HOST, IW_CORE_DB_PORT, IW_CORE_DB_NAME, IW_CORE_DB_USER, IW_CORE_DB_PASSWORD
#   IW_E2E_OLLAMA_URL (optional, for seed)
#
# Fails fast on migration or seed errors; uvicorn replaces the shell via exec.

set -euo pipefail

echo "[e2e] waiting for DB at ${IW_CORE_DB_HOST}:${IW_CORE_DB_PORT}..."
for _ in $(seq 1 60); do
    if uv run python -c "
import os, sys
import psycopg
try:
    with psycopg.connect(
        host=os.environ['IW_CORE_DB_HOST'],
        port=int(os.environ['IW_CORE_DB_PORT']),
        dbname=os.environ['IW_CORE_DB_NAME'],
        user=os.environ['IW_CORE_DB_USER'],
        password=os.environ['IW_CORE_DB_PASSWORD'],
        connect_timeout=2,
    ) as c:
        c.execute('SELECT 1')
    sys.exit(0)
except Exception as e:
    sys.exit(1)
" 2>/dev/null; then
        echo "[e2e] DB is reachable"
        break
    fi
    sleep 1
done

echo "[e2e] applying migrations..."
uv run alembic upgrade heads

echo "[e2e] seeding project + architecture map..."
uv run python scripts/e2e_seed.py

# Create an empty LanceDB vectors dir so the /code/qa index-exists check
# passes. Matches the CodeIndexJob(status=completed) row inserted by the
# seed. The work-item-aware pipeline reads from Postgres FTS + design docs,
# not from a populated LanceDB, so an empty dir is sufficient for S18.
INDEX_DIR="${IW_CORE_INDEX_PATH:-/tmp/iw-core-e2e-index}/iw-ai-core/vectors"
echo "[e2e] ensuring LanceDB vectors dir exists at ${INDEX_DIR}..."
mkdir -p "${INDEX_DIR}"

echo "[e2e] starting dashboard on :9900..."
exec uv run uvicorn dashboard.app:create_app --factory --host 0.0.0.0 --port 9900
