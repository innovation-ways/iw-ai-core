# CR-00083_S01_Backend_prompt

**Work Item**: CR-00083 -- Performance-budget test layer — pytest-benchmark assertions with regression-alert baselines
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures (Ryuk-managed).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00083 --json`.
- `ai-dev/work/CR-00083/CR-00083_CR_Design.md` -- Design document (read first).
- `pyproject.toml` — current `[dependency-groups] dev` and `[tool.pytest.ini_options]` sections.

## Output Files

- `ai-dev/work/CR-00083/reports/CR-00083_S01_Backend_report.md` -- Step report.

## Context

You are implementing **S01** of CR-00083 — the smallest possible step: add the `pytest-benchmark` dependency, register the `perf` marker, and append the marker to `addopts` so default test runs do NOT collect perf modules. S02 builds the perf package skeleton + daemon module on top of this groundwork.

This step is intentionally tiny — the design splits S01/S02 so the agent's context budget for the larger S02 stays bounded (CR-00076 lesson: monolithic test-infrastructure steps blow context windows).

## Requirements

### 1. Add `pytest-benchmark` dependency

Edit `pyproject.toml` `[dependency-groups] dev`: add `"pytest-benchmark>=4.0,<5"`. Regenerate `uv.lock` via `uv lock`. Verify `uv run python -c "import pytest_benchmark"` exits 0.

### 2. Register the `perf` marker and exclude it from default runs

In `pyproject.toml` `[tool.pytest.ini_options]`:

- Add `"perf: performance budget tests — excluded from default unit/integration runs; run via make test-perf*"` to `markers`.
- Modify `addopts` from the current value (e.g., `-m 'not browser and not quarantine'`) to append ` and not perf`, yielding `-m 'not browser and not quarantine and not perf'`. Preserve all other `addopts` flags verbatim.

### 3. Verify the marker excludes perf tests from default runs

Since `tests/perf/` does NOT exist yet (S02 creates it), the verification has two parts:

```bash
# Create a temporary stub to verify the addopts exclusion works:
mkdir -p tests/perf
printf 'import pytest\n\n@pytest.mark.perf\ndef test_stub():\n    assert True\n' > tests/perf/test_stub_marker_check.py

# Default invocation must NOT collect the stub:
uv run pytest tests/perf/ --collect-only --no-cov 2>&1 | tail -5
# Expected: "no tests collected" or the stub deselected by `-m 'not perf'`

# -m perf invocation MUST collect it:
uv run pytest tests/perf/ -m perf --collect-only --no-cov 2>&1 | tail -5
# Expected: "1 test collected"

# Clean up the stub — S02 owns the real tests/perf/ contents:
rm -rf tests/perf/
```

The stub is a marker-wiring smoke test only — it must NOT be committed. If `git status` shows `tests/perf/` after cleanup, delete it before continuing.

## Project Conventions

Read CLAUDE.md for the marker naming and `addopts` conventions in `pyproject.toml`.

## TDD Requirement

This step is dependency + configuration only — there is no behavioural artefact. Use:

> `tdd_red_evidence: "n/a — dependency + marker configuration only; behavioural perf tests are introduced in S02 onward"`

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix formatting on touched files.
2. `make typecheck` — zero errors on touched files.
3. `make lint` — zero errors on touched files.

## Test Verification (NON-NEGOTIABLE)

Run ONLY the marker-isolation smoke check shown above (the temporary stub).

Do NOT run `make test-unit`, `make test-integration`, or `make check` — those are S10/S11/S12 QV gates equivalents in the renumbered manifest (S11/S12/S13).

## Scope discipline (CR-00083 hard rule)

You MUST NOT create `tests/perf/` (S02 owns that), modify any production code under `orch/`, `dashboard/`, `executor/`, `scripts/`, `bin/`, `templates/`, or touch the Makefile (S02/S03 add Makefile targets).

Files you are permitted to touch in this step:
- `pyproject.toml`
- `uv.lock`

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "pyproject.toml",
    "uv.lock"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "marker-isolation stub: default run deselected (0 collected); -m perf run collected 1; stub deleted",
  "tdd_red_evidence": "n/a — dependency + marker configuration only; behavioural perf tests are introduced in S02 onward",
  "blockers": [],
  "notes": "pytest-benchmark resolved at <version>; uv.lock regenerated; marker registered and excluded from default `addopts`."
}
```
