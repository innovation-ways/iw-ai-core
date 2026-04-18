#!/usr/bin/env bash
# Tear down the isolated E2E stack.
#
# Called by the daemon on step-done / step-fail / timeout paths.
# Idempotent and best-effort — must never fail-fast (env is considered
# torn down if the project namespace does not exist).

set -uo pipefail

: "${COMPOSE_PROJECT_NAME:?COMPOSE_PROJECT_NAME must be set}"

echo "[e2e_down] project=${COMPOSE_PROJECT_NAME}"

docker compose -f docker-compose.e2e.yml -p "${COMPOSE_PROJECT_NAME}" \
    down --remove-orphans --volumes --timeout 20 || true

exit 0
