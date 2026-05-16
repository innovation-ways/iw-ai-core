# CR-00054 — S02 Pipeline Report

## What was done

- Updated `Dockerfile.e2e` to install an `opencode` shim at `/usr/local/bin/opencode` (as root, before `USER app`) that runs:
  - `uv run python /app/scripts/e2e_opencode_stub.py "$@"`
- Added the required CR-00054 comment block above the shim layer explaining why the real OpenCode binary is not installed in E2E.
- Added a dependency note above `COPY --chown=app:app . .` documenting that this copy must include `.opencode/config.json`.
- Added build-time validation immediately after the second `RUN uv sync --frozen --no-dev`:
  - `RUN /usr/local/bin/opencode --selftest`

## Files changed

- `Dockerfile.e2e`

## Test / validation results

- Python tests: n/a (Dockerfile-only step)
- BuildKit syntax/lint check executed:
  - `docker build --target base -f Dockerfile.e2e --check . 2>&1 | head -20`
  - Result: command ran successfully with no Dockerfile check errors in output.

## Issues / observations

- `scripts/e2e_opencode_stub.py` already includes `--selftest`, so no blocker was encountered.
- `.dockerignore` does not exclude `.opencode/`, so no `.dockerignore` change was required.
