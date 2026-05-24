# CR-00086_S03_Backend_prompt

**Work Item**: CR-00086 -- Self-dashboarding of test health
**Step**: S03
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

  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch DB on port 5433. The S01 migration is already applied in the testcontainer via the conftest fixture; you do not need to apply anything manually.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00086 --json`.
- `ai-dev/active/CR-00086/CR-00086_CR_Design.md` -- Design document (read Desired Behavior, AC2, AC3, Notes)
- `ai-dev/work/CR-00086/reports/CR-00086_S01_Database_report.md` -- S01 report
- `orch/db/models.py` -- new `TestHealthSnapshot` model (from S01)
- `orch/coverage_service.py` -- existing coverage parser; **reuse, do not re-implement**
- `scripts/flake_detect_aggregate.py` (CR-00061) -- flaky-count source format reference
- `tests/assertion_free_baseline.txt` (CR-00046) -- baseline-size source
- Any recent mutation-results artefact (CR-00059/CR-00080 shape) under `tests/output/`

## Output Files

- `ai-dev/work/CR-00086/reports/CR-00086_S03_Backend_report.md` -- Step report
- `orch/test_health_service.py` (new)
- `orch/cli/test_health_commands.py` (new; or extend `orch/cli/__init__.py` if the project mounts subcommands via decorator)
- `tests/integration/test_test_health_service.py` (new)
- `tests/unit/test_test_health_service.py` (new)

## Context

You are implementing the **Backend service + CLI** step of **CR-00086**. The new service reads four artefact sources (mutation JSON, coverage XML, flaky log, assertion baseline) and writes snapshots to the `test_health_snapshots` table that S01 created. A new `iw test-health-capture` CLI command drives the capture.

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md` first.

## Requirements

### 1. orch/test_health_service.py

Expose three public functions:

- `read_sources(project_slug: str) -> dict[str, tuple[float, dict] | None]` — returns the latest value+meta tuple for each of the four metric keys: `mutation_score`, `coverage_pct`, `flaky_test_count`, `assertion_baseline_size`. A missing source returns `None` for that key and logs a single WARNING line per missing source. **Never raise** on a missing source.
- `capture_snapshot(session, project_id: int, metric: str, value: float, meta: dict) -> TestHealthSnapshot` — upsert on `(project_id, metric, ts_truncated_to_minute)`. Re-running within the same minute on identical inputs is a no-op and returns the existing row.
- `latest(session, project_id: int) -> dict[str, TestHealthSnapshot]` and `trend(session, project_id: int, metric: str, limit: int = 30) -> list[TestHealthSnapshot]`.

**Mutation-JSON adapter**: parse BOTH the CR-00080 widened-scope shape AND the CR-00059 spike shape. Use a small dispatch behind a `_parse_mutation_json(payload: dict) -> tuple[float, dict]` helper so a future shape change is a one-file edit. If the JSON cannot be parsed by either, return None and log WARNING (do NOT raise).

**Coverage reader**: reuse `orch/coverage_service.py`'s existing path resolution. Do NOT re-implement coverage.xml parsing.

**Flaky reader**: invoke or read the output of `scripts/flake_detect_aggregate.py`. If the script emits JSON or counts on stdout, parse that; if it writes a summary file, read the latest one. Mirror the contract the script already documents.

**Baseline reader**: line-count `tests/assertion_free_baseline.txt`. Subtract comment-only lines if the file uses leading-`#` comments (check the file).

### 2. iw test-health-capture CLI command

Under `orch/cli/`, add a new module (or extend an existing one) exposing a Typer command `test-health-capture --project <slug>` that:

1. Looks up the project row by slug. If missing, exit 2 with a clear error message.
2. Calls `read_sources(slug)`.
3. For each metric whose value is not None, calls `capture_snapshot(...)`.
4. Prints a JSON summary to stdout: `{"project": slug, "captured": [{"metric": ..., "value": ..., "ts": ...}, ...], "skipped": [{"metric": ..., "reason": ...}, ...]}`.
5. Returns exit code 0 on success (including no-op captures); 1 only on DB errors.

Wire the command into the Typer app the way other CLI commands are wired (read `orch/cli/__init__.py` for the pattern).

### 3. Jobs aggregator hook (light)

S05 adds the full Jobs view integration, but `capture_snapshot` should write a small row to whatever telemetry table the aggregator scans (look at how `CodeIndexJob` rows are written when a code-index run starts/ends — replicate the pattern at a minimum). If the aggregator reads directly from `test_health_snapshots` (one job row per capture invocation), document that in your report so S05 can wire the aggregator's union query.

### 4. TDD tests (RED FIRST)

Write these tests BEFORE the production code and capture the RED run snippet in `tdd_red_evidence`:

- `tests/unit/test_test_health_service.py`:
  - `test_read_mutation_score_new_shape` — feed a JSON payload in CR-00080's shape, assert the parsed value matches.
  - `test_read_mutation_score_legacy_shape` — feed a JSON payload in CR-00059's shape, assert the parser still works.
  - `test_read_missing_source_returns_none` — point the reader at a non-existent path, assert `None` and a WARNING log line.
  - `test_baseline_line_count_strips_comments` — feed a baseline file with mixed comment + entry lines, assert correct count.
- `tests/integration/test_test_health_service.py` (testcontainer):
  - `test_capture_writes_four_snapshots` — call the CLI command via Typer's `CliRunner` with a seeded project + canned source artefacts; assert 4 rows in the DB and the JSON summary matches.
  - `test_idempotent_within_minute` — call capture twice within the same minute; assert exactly one row per `(project, metric, ts_minute)`.
  - `test_latest_and_trend` — insert 35 snapshots for one metric, assert `latest()` returns the most recent and `trend(limit=30)` returns 30 in DESC ts order.
  - `test_missing_source_skips_that_metric` — call capture with three sources present and one missing; assert 3 rows, 1 entry in `skipped[]`, exit code 0.

## Project Conventions

Read the project's `CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md`:

- Typer CLI patterns; never hardcode ports/URLs
- Session management (the `Session` factory is in `orch/db/session.py` — reuse)
- Logging via the project logger, not `print`
- Testcontainer fixtures (never connect to port 5433 from tests)

## TDD Requirement

Write failing tests first; capture the RED run; then implement. RED MUST be an `AssertionError` / `NotImplementedError` / `AttributeError` from missing implementation — NOT an `ImportError`, `SyntaxError`, fixture error, or collection error.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

Populate the `preflight` object.

## Test Verification (NON-NEGOTIABLE)

Targeted only:

```bash
uv run pytest tests/integration/test_test_health_service.py tests/unit/test_test_health_service.py -v
```

Do NOT run `make test-integration`. That is S13's job.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/test_health_service.py",
    "orch/cli/test_health_commands.py",
    "orch/cli/__init__.py",
    "tests/integration/test_test_health_service.py",
    "tests/unit/test_test_health_service.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/integration/test_test_health_service.py::test_capture_writes_four_snapshots — AttributeError: module 'orch' has no attribute 'test_health_service'  // captured RED run",
  "blockers": [],
  "notes": ""
}
```
