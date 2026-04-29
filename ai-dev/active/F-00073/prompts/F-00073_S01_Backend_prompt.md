# F-00073_S01_Backend_prompt

**Work Item**: F-00073 -- Smoke Gate + Active Test CI + Logging Tests
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies. Testcontainer fixtures are exempt.)

## Input Files

- `uv run iw item-status F-00073 --json`
- `ai-dev/active/F-00073/F-00073_Feature_Design.md`
- `pyproject.toml` — markers, deps, coverage threshold (set up by F-00069)
- `Makefile` — existing test targets
- `tests/conftest.py` — fixture patterns
- `tests/CLAUDE.md` — strict rules
- `dashboard/app.py` — for app-factory smoke
- `dashboard/routers/healthz.py` — for /healthz smoke
- `orch/config.py` — for credential redaction inspection
- `orch/db/session.py` — for engine URL handling
- `.github/workflows/compliance-scan.yml` — pattern reference for SHA pins, permissions, set -euo pipefail
- `docker-compose.bootstrap.yml` — Postgres major version for the CI service container

## Output Files

- Modified: `pyproject.toml`, `Makefile`, various existing test files (smoke marker additions)
- New: `tests/unit/test_logging.py`, `.github/workflows/test-quality.yml`
- `ai-dev/active/F-00073/reports/F-00073_S01_Backend_report.md`

## Context

Implement smoke marker, smoke tests, make target, CI workflow, and logging tests. Tests-step deliverables are owned by S03; reviews by S02/S04/S05; QV by S06+. Frontend / browser verification is not in scope.

**This feature depends on F-00069.** When this prompt runs, F-00069 has already merged, so:
- `pytest-xdist` is in dev deps.
- `[tool.pytest.ini_options] addopts` includes `--cov` flags.
- `[tool.coverage.report] fail_under` is set to a known floor.
- `make test-parallel` exists.
- `dashboard/services/coverage_service.py` exists.
- `make e2e-{health,logs,stats}` exist.

DO NOT modify any of those — they are F-00069 territory. Just consume them.

## Requirements

### 1. Register the `smoke` marker

In `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "..."   # whatever F-00069 set; do not change
markers = [
    "integration: marks tests as integration (require docker/testcontainer)",
    "smoke: fast critical-path tests; ~10 covering core flows; run via `make smoke`",
]
```

### 2. Mark / write the smoke set

Identify and mark existing tests where possible. Write new ones ONLY when no existing test covers the path. The 10-test set:

| # | Path | Action |
|---|---|---|
| 1 | Dashboard app factory creates without error | Likely exists in `tests/dashboard/test_app.py` or similar — mark; if not, write a 5-line test |
| 2 | `/healthz/identity` returns 200/503 with expected JSON shape | Likely exists — mark |
| 3 | Project list page renders | Likely exists in `tests/dashboard/` — mark |
| 4 | Queue/history page renders | Mark existing or write |
| 5 | `iw batch-create` against fixture work item creates DB row | Likely exists in `tests/integration/` — mark |
| 6 | Daemon SIGHUP triggers project-registry reload | Likely exists in `tests/unit/daemon/` — mark |
| 7 | `iw db-identity check` against testcontainer | Likely exists — mark |
| 8 | `iw --help` exits 0 | Likely exists or trivial to write |
| 9 | `from orch.db.models import Base` works | Trivial — write a 3-line test |
| 10 | `dashboard.services.coverage_service.load_coverage()` returns empty-state when file missing | Already in F-00069's tests — add the smoke marker |

Run `pytest -m smoke --collect-only -q` after marking to confirm exactly 10 (±2) are collected.

For each marked existing test, ensure the marker is additive (`@pytest.mark.smoke` ON TOP of any existing `@pytest.mark.integration`).

Each test must run in <5s. If marking a test makes the suite slow, drop the marker and write a leaner one.

### 3. `make smoke` target

```makefile
smoke:
	uv run pytest tests -m smoke -v --no-header --strict-markers
```

`--strict-markers` makes typo-detection automatic. No coverage flags here (overrides any addopts coverage flags via `--no-cov` if needed — verify behavior).

If the existing `addopts` in pyproject forces `--cov`, add `--no-cov` to the smoke command:

```makefile
smoke:
	uv run pytest tests -m smoke -v --no-header --strict-markers --no-cov
```

Add `smoke` to `.PHONY`.

### 4. `tests/unit/test_logging.py`

Write tests asserting:

- `logging.getLogger("orch").level` and propagation behavior is what we expect (likely INFO, propagating up).
- Same for `logging.getLogger("dashboard")`.
- Credential redaction: take a fixture URL like `postgresql+psycopg://iw:secretpassword@localhost:5432/iw_ai_core`, pass it through whatever the project does to render it (e.g. `engine.url` or a `_safe_url()` helper if it exists), assert `"secretpassword"` does NOT appear in the result. If no helper exists, test that constructing an engine doesn't expose the password in `repr(engine)`.
- If no logging configuration exists yet at all, the tests assert what SHOULD exist (per `CLAUDE.md`). It's acceptable for this test file to be a forcing function for a real fix.

If, while writing these tests, you discover credentials are leaking in any log path, **STOP, write the test as RED, raise a blocker** so the leak gets fixed before the test goes GREEN.

### 5. `.github/workflows/test-quality.yml`

```yaml
# Active test + quality CI — runs on every PR and push to main.
#
# Action versions are pinned to commit SHAs; failure of any job blocks merge.

name: Test & Quality

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  lint-typecheck:
    name: Lint, format, typecheck
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<PIN>
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@<PIN>
      - run: uv sync --frozen
      - run: make lint
      - run: make format-check || make format   # whichever the Makefile defines
      - run: make typecheck

  unit:
    name: Unit tests + coverage
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<PIN>
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@<PIN>
      - run: uv sync --frozen
      - run: make test-unit   # consumes F-00069's --cov-fail-under threshold
      - name: Upload coverage XML artefact
        if: always()
        uses: actions/upload-artifact@<PIN>
        with:
          name: coverage-xml
          path: tests/output/coverage/coverage.xml

  integration:
    name: Integration tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:<MAJOR>   # match docker-compose.bootstrap.yml
        env:
          POSTGRES_USER: iw
          POSTGRES_PASSWORD: iw
          POSTGRES_DB: iw_ai_core
        ports:
          - 5433:5432             # match production port for any port-aware tests
        options: >-
          --health-cmd "pg_isready -U iw"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
    env:
      IW_CORE_DB_HOST: localhost
      IW_CORE_DB_PORT: "5433"
      IW_CORE_DB_NAME: iw_ai_core
      IW_CORE_DB_USER: iw
      IW_CORE_DB_PASSWORD: iw
    steps:
      - uses: actions/checkout@<PIN>
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@<PIN>
      - run: uv sync --frozen
      - run: make test-integration

  smoke:
    name: Smoke
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:<MAJOR>
        env:
          POSTGRES_USER: iw
          POSTGRES_PASSWORD: iw
          POSTGRES_DB: iw_ai_core
        ports:
          - 5433:5432
        options: >-
          --health-cmd "pg_isready -U iw"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
    env:
      IW_CORE_DB_HOST: localhost
      IW_CORE_DB_PORT: "5433"
      IW_CORE_DB_NAME: iw_ai_core
      IW_CORE_DB_USER: iw
      IW_CORE_DB_PASSWORD: iw
    steps:
      - uses: actions/checkout@<PIN>
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@<PIN>
      - run: uv sync --frozen
      - run: make smoke
```

Resolve `<PIN>` and `<MAJOR>` as in F-00071 / F-00072. Add trailing `# vN.N.N` comments on each pin.

NOTE: Some smoke tests may not need a DB. The smoke job uses the same Postgres service container as integration so any smoke test that needs DB still works. Acceptable trade-off.

### 6. Smoke regression guard

S03 owns this — do not write the test in S01. But verify your changes don't break F-00069's existing `tests/unit/test_make_targets.py` (S05 of F-00069). Run that test and confirm it still passes.

### 7. NOT in this step

- Modifications to F-00069's coverage / xdist / dashboard config (already shipped).
- New observability infrastructure.
- Codecov upload (skipped per design).

## Project Conventions

- `[tool.pytest.ini_options]` markers are list-of-strings.
- SHA-pin every action with trailing version comment.
- `set -euo pipefail` if any complex run-step shell.
- Match the live-DB-guard rules — testcontainers OK, real port 5433 NOT.

## TDD Requirement

- For each smoke test: write RED first by breaking the path it covers (or marking a test that can't actually run in <5s), confirm fail, fix.
- For logging tests: write RED first.

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit`
5. `make smoke`
6. `make test-integration`

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00073",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "pyproject.toml",
    "Makefile",
    "tests/unit/test_logging.py",
    ".github/workflows/test-quality.yml"
  ],
  "smoke_test_inventory": [
    {"id": 1, "test": "<file::test_name>", "reused_existing": true, "wallclock_ms": 0}
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "smoke_summary": "10 collected, total wallclock: <Xs>",
  "logging_test_findings": [],
  "action_pins_resolved": [],
  "blockers": [],
  "notes": ""
}
```

If any logging test reveals a real credential leak, populate `logging_test_findings` with the file:line of the leak path and use `completion_status: blocked` until S02/S05 decide whether the leak fix belongs in this feature or is a separate Incident.
