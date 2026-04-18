#!/usr/bin/env bash
# Bring up an isolated E2E stack for a browser_verification step.
#
# Called by the daemon via `.iw-orch.json.browser_verification.env_up_command`.
# Environment variables set by orch.daemon.browser_env.allocate_browser_env:
#   COMPOSE_PROJECT_NAME   — unique per (project_id, item_id), e.g. iw-ai-core-e2e-cr00009
#   E2E_FRONTEND_PORT      — host port for the dashboard
#   E2E_DB_PORT            — host port for the isolated postgres
#   E2E_API_PORT           — unused (dashboard is frontend+API in one process)
#   E2E_REDIS_PORT         — unused
#   IW_BROWSER_BASE_URL    — http://localhost:${E2E_FRONTEND_PORT}
#   IW_ITEM_ID             — work item id (for logs)
#
# CWD is the worktree root (daemon sets it via subprocess cwd=worktree_path).
# Logs are tee'd to ai-dev/logs/<item>_<step>_browser_env_up.log by the daemon.

set -euo pipefail

: "${COMPOSE_PROJECT_NAME:?COMPOSE_PROJECT_NAME must be set}"
: "${E2E_FRONTEND_PORT:?E2E_FRONTEND_PORT must be set}"
: "${E2E_DB_PORT:?E2E_DB_PORT must be set}"
: "${IW_BROWSER_BASE_URL:?IW_BROWSER_BASE_URL must be set}"

echo "[e2e_up] project=${COMPOSE_PROJECT_NAME} dashboard=${E2E_FRONTEND_PORT} db=${E2E_DB_PORT}"

# Stale containers from a prior failed run of THIS compose project — clean them up
# before bringing the stack up, so we don't race on the fixed internal ports (9900, 5432).
docker compose -f docker-compose.e2e.yml -p "${COMPOSE_PROJECT_NAME}" down --remove-orphans --volumes >/dev/null 2>&1 || true

# Bring the stack up. --wait blocks until all services with healthchecks
# are healthy (up to their per-service retry budget). --build ensures the
# image reflects the worktree's current source.
docker compose -f docker-compose.e2e.yml -p "${COMPOSE_PROJECT_NAME}" up -d --build --wait

# Belt-and-braces: probe the dashboard from the host. --wait should have
# blocked until the container's healthcheck passed, but container→host port
# binding can briefly lag on some Docker Desktop versions.
echo "[e2e_up] probing ${IW_BROWSER_BASE_URL}/health..."
for _ in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 2 "${IW_BROWSER_BASE_URL}/health" >/dev/null; then
        echo "[e2e_up] stack healthy"
        exit 0
    fi
    sleep 1
done

echo "[e2e_up] dashboard never became healthy at ${IW_BROWSER_BASE_URL}/health"
docker compose -f docker-compose.e2e.yml -p "${COMPOSE_PROJECT_NAME}" ps || true
docker compose -f docker-compose.e2e.yml -p "${COMPOSE_PROJECT_NAME}" logs --tail 100 || true
exit 1
