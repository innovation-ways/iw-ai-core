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

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. If your work suggests you need one, STOP — that's a design violation, not a step deliverable.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00083 --json`.
- `ai-dev/work/CR-00083/CR-00083_CR_Design.md` -- Design document (read first).
- `orch/daemon/main.py` — `Daemon` class, `_poll_cycle` method (~line 525).
- `tests/conftest.py` + `tests/integration/conftest.py` — existing testcontainer fixture patterns.
- `tests/integration/data_layer/` — recent CR-00076 example of a tightly-scoped test package; mirror its layout.

## Output Files

- `ai-dev/work/CR-00083/reports/CR-00083_S01_Backend_report.md` -- Step report.

## Context

You are implementing **S01** of CR-00083 — the daemon poll-loop perf module + the `pytest-benchmark` dependency + the package skeleton + the first Makefile target.

Read the design document **first**. Then read CLAUDE.md and `docs/IW_AI_Core_Testing_Strategy.md` for context on existing test layers and the testcontainer/FTS conventions.

## Requirements

### 1. Add `pytest-benchmark` dependency

Edit `pyproject.toml` `[dependency-groups] dev`: add `"pytest-benchmark>=4.0,<5"`. Regenerate `uv.lock` via `uv lock`. Verify `uv run python -c "import pytest_benchmark"` exits 0.

### 2. Register the `perf` marker and exclude it from default runs

In `pyproject.toml` `[tool.pytest.ini_options]`:
- Add `"perf: performance budget tests — excluded from default unit/integration runs; run via make test-perf*"` to `markers`.
- Modify `addopts` from the current value (e.g., `-m 'not browser and not quarantine'`) to append ` and not perf`, yielding `-m 'not browser and not quarantine and not perf'`. Preserve all other `addopts` flags verbatim.

### 3. Create the `tests/perf/` package skeleton

- `tests/perf/__init__.py` — empty (Python package marker).
- `tests/perf/conftest.py` — registers the `perf` marker for all collected tests in the package (use `pytestmark = pytest.mark.perf` at module level in each test file OR a `pytest_collection_modifyitems` hook in conftest that auto-applies it; prefer the auto-apply hook so individual test authors can't forget). Provide a `seeded_orch_db` testcontainer fixture: spins up `postgres:16`, replaces `postgresql+psycopg2://` with `postgresql+psycopg://`, runs `Base.metadata.create_all()` + `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`, seeds 1 project + 3 work items (one in each of three different states) + 1 batch + 1 active worktree-stub row. The fixture should be `scope="session"` for amortised setup cost across all perf tests.
- `tests/perf/baselines/` — directory (committed via a `.gitkeep` or via the baseline JSONs themselves).

### 4. Create `tests/perf/test_daemon_poll_loop.py`

Structure:

```python
"""Daemon poll-loop performance budget.

Methodology: measures one `Daemon._poll_cycle()` iteration against a seeded
testcontainer DB. Budget = initial_mean × 1.5 (50% headroom rule from CR-00083).
Uses `mean` because σ/μ < 0.3 in the initial 10-run sample (record actual ratio
below). If a future change pushes σ/μ above 0.3, switch to `min` and update
this docstring.

Initial measurement (2026-05-24, S01 run): mean = <X> ms, σ/μ = <Y>.
"""
import pytest
from orch.daemon.main import Daemon
# ... seeded_orch_db fixture imported from conftest

BUDGET_MS = <ceil(initial_mean * 1.5)>  # frozen 2026-05-24 — operator-only updates via CR


def test_daemon_poll_cycle_within_budget(benchmark, seeded_orch_db):
    daemon = _build_minimal_daemon(seeded_orch_db)  # mocks keep-alive + doc-job pollers
    result = benchmark.pedantic(
        daemon._poll_cycle,
        rounds=10,
        warmup_rounds=5,
    )
    assert benchmark.stats.stats.mean * 1000 < BUDGET_MS, (
        f"daemon poll-cycle mean {benchmark.stats.stats.mean * 1000:.1f} ms "
        f"exceeds budget {BUDGET_MS} ms"
    )
```

The `_build_minimal_daemon` helper should construct a `Daemon` instance against the seeded DB and mock the keep-alive poller, doc-job poller, and chat-summarisation poller (they each spin up their own infra). The goal is to isolate `_poll_cycle`'s own latency.

### 5. Generate and commit the daemon baseline JSON

Run:

```bash
uv run pytest tests/perf/test_daemon_poll_loop.py -v --benchmark-save=daemon --benchmark-storage=file://tests/perf/baselines -m perf --no-cov
```

This produces `tests/perf/baselines/Linux-CPython-*/daemon.json` (or similar). Commit this file. The compare flag (`--benchmark-compare=daemon --benchmark-compare-fail=mean:25%`) will resolve against it on future runs.

### 6. Add Makefile target `test-perf-daemon`

```makefile
.PHONY: test-perf-daemon
test-perf-daemon:  ## Run daemon poll-loop performance budget test
	uv run pytest tests/perf/test_daemon_poll_loop.py -v --benchmark-compare=daemon --benchmark-compare-fail=mean:25% --benchmark-storage=file://tests/perf/baselines -m perf --no-cov
```

Add `test-perf-daemon` to the top-level `.PHONY` aggregation list (line ~6 of the Makefile).

### 7. RED-first evidence

Your `tdd_red_evidence` field must read:

> `daemon poll-loop initial mean = <X> ms (σ/μ = <Y>); BUDGET_MS = ceil(X * 1.5) = <Z> ms; final test passes with mean = <W> < Z (committed to tests/perf/baselines/.../daemon.json).`

This is your behavioural-test RED phase: the test fails until the budget constant + baseline are in place.

## Project Conventions

Read CLAUDE.md for:
- Testcontainer URL replacement rule (`postgresql+psycopg2://` → `postgresql+psycopg://`).
- FTS_FUNCTION_SQL + FTS_TRIGGER_SQL requirement after `Base.metadata.create_all()`.
- The live-DB write guard (NEVER point a test at port 5433).
- Marker naming and `addopts` conventions in `pyproject.toml`.

Read `tests/CLAUDE.md` and `docs/IW_AI_Core_Testing_Strategy.md` §2-§4 before writing the conftest fixture.

## TDD Requirement

The perf test IS the new behavioural artefact. RED evidence = the initial-measurement → budget-set → final-green narrative recorded in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix formatting on touched files.
2. `make typecheck` — zero errors on touched files (errors elsewhere are pre-existing).
3. `make lint` — zero errors on touched files.

## Test Verification (NON-NEGOTIABLE)

Run ONLY:

```bash
uv run pytest tests/perf/test_daemon_poll_loop.py -v --benchmark-compare=daemon --benchmark-compare-fail=mean:25% --benchmark-storage=file://tests/perf/baselines -m perf --no-cov
```

Do NOT run `make test-unit`, `make test-integration`, or `make check` — those are S10/S11/S12 QV gates.

## Scope discipline (CR-00083 hard rule)

You MUST NOT modify any production code under `orch/`, `dashboard/`, `executor/`, `scripts/`, `bin/`, `templates/`. If your work suggests a production-code change, STOP and raise a blocker — the design's Notes section explicitly forbids in-CR production fixes (file an Incident instead).

Files you are permitted to touch in this step:
- `pyproject.toml`
- `uv.lock`
- `tests/perf/__init__.py` (new)
- `tests/perf/conftest.py` (new)
- `tests/perf/test_daemon_poll_loop.py` (new)
- `tests/perf/baselines/**/*.json` (new — generated)
- `Makefile`

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "pyproject.toml",
    "uv.lock",
    "tests/perf/__init__.py",
    "tests/perf/conftest.py",
    "tests/perf/test_daemon_poll_loop.py",
    "tests/perf/baselines/.../daemon.json",
    "Makefile"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "1 passed (daemon perf test), 0 failed",
  "tdd_red_evidence": "daemon poll-loop initial mean = <X> ms (σ/μ = <Y>); BUDGET_MS = ceil(X * 1.5) = <Z> ms; final passes with mean = <W> < Z (baseline committed)",
  "blockers": [],
  "notes": "Initial measurement recorded; budget frozen at <Z> ms; mean-vs-min choice = mean (σ/μ = <Y> < 0.3)."
}
```
