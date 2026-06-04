#!/usr/bin/env bash
# Tear down the isolated E2E stack.
#
# Called by the daemon on step-done / step-fail / timeout paths.
# Idempotent and best-effort — must never fail-fast (env is considered
# torn down if the project namespace does not exist).
#
# `--rmi local` removes the per-project images that `e2e_up.sh --build`
# produced (e.g. iw-ai-core-e2e-<item>-e2e-dashboard:latest). Without it
# every browser_verification run leaves ~2.2 GB of images behind, which
# accumulate across work items until the host disk fills up. `local` only
# touches images built by this compose project — base images pulled from
# registries (postgres, ollama, etc.) are kept.

set -uo pipefail

: "${COMPOSE_PROJECT_NAME:?COMPOSE_PROJECT_NAME must be set}"

echo "[e2e_down] project=${COMPOSE_PROJECT_NAME}"

docker compose -f docker-compose.e2e.yml -p "${COMPOSE_PROJECT_NAME}" \
    down --remove-orphans --volumes --rmi local --timeout 20 || true

# `--rmi local` only removes the *currently tagged* per-project images. Each
# `e2e_up.sh --build` cycle however orphans the previous build (it loses its
# tag to the new layer), and those untagged remnants still carry the
# com.docker.compose.project label.  Sweep them by label so the disk
# does not bloat by ~2 GB per fix-cycle re-provision. Best-effort.
dangling=$(docker images -a \
    --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" -q \
    2>/dev/null || true)
if [[ -n "${dangling}" ]]; then
    echo "[e2e_down] pruning $(echo "${dangling}" | wc -l) leftover image(s) for ${COMPOSE_PROJECT_NAME}"
    echo "${dangling}" | xargs -r docker rmi -f >/dev/null 2>&1 || true
fi

exit 0
