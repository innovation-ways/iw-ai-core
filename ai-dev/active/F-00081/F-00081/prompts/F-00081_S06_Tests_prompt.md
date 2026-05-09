# F-00081_S06_Tests_prompt

**Work Item**: F-00081 -- Per-Item / Per-Step Agent + Model Override
**Step**: S06
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures via `tests/conftest.py` are exempt. See `tests/CLAUDE.md`.

## ⛔ Migrations: agents generate, daemon applies

Use the testcontainer-applied schema; do NOT touch live alembic.

## Input Files

- `uv run iw item-status F-00081 --json`.
- `ai-dev/active/F-00081/F-00081_Feature_Design.md` — every Boundary Behavior row and every Invariant must have at least one test.
- All previous step reports under `ai-dev/active/F-00081/reports/`.
- Files changed by S01–S05.
- `tests/CLAUDE.md` for the project's pytest patterns (testcontainers, FTS triggers, psycopg URL replacement).

## Output Files

- `ai-dev/active/F-00081/reports/F-00081_S06_Tests_report.md`.
- New tests in `tests/integration/`, `tests/unit/`, and `tests/dashboard/`.

## Context

Steps S02–S05 each wrote a focused test set covering their own work. S06 fills the gaps: cross-layer integration, the boundary-behaviour table, and the explicit AC1–AC8 acceptance scenarios. **You should not duplicate tests written by S02–S05** — read those reports' `files_changed` and inspect the existing tests first. Add only what is missing.

## Requirements

### 1. Cross-layer integration tests

Add `tests/integration/test_f00081_cascade.py`:

- **AC1** Default-only path: register an item, no overrides → daemon-launch path resolves to `is_default=true` row; `step_runs.agent_runtime_option_id` = default row id; the recorded `command` contains `--model minimax`.
- **AC2** Item override: set item's `agent_runtime_option_id` to (claude, opus) row → next launched step records that pair, command begins with `claude -p`, includes `--model claude-opus-4-7`.
- **AC3** Step beats item: set item to (claude, opus), step S03 to (opencode, minimax) → S03 records (opencode, minimax).
- **AC5** Mid-flight: while a step is `in_progress`, mutate the item's `agent_runtime_option_id`, run the daemon launch helper for the *next* pending step, assert the running step's `step_runs` row is unchanged and the next step records the new pair.

Tests must hit the testcontainer DB (no mocks, per CLAUDE.md). They should construct the daemon launch path either by calling the resolver + StepRun-creation helper directly or by invoking the launch site's internal function (whichever S02 made testable).

### 2. Boundary-behavior coverage

Add `tests/integration/test_f00081_boundaries.py` with one test per row of the design's Boundary Behavior table:

- Catalogue empty (no rows match cli_tool) → resolver falls back to default, logs warning.
- Override points to disabled row → ignored, fallback used, warning logged.
- Bulk PATCH on item with zero editable steps → 200, `affected: 0`, **no** DaemonEvent emitted.
- Step transitions mid-PATCH (race) → single-step PATCH returns 409; bulk skips and proceeds.
- projects.toml references missing pair → daemon load logs warning, falls back.
- Pre-feature item shape (NULL FKs) → resolver returns project default → catalogue default.
- Catalogue row deletion attempted while in use → DB raises FK violation (RESTRICT).
- Override mutation on terminal item → 400.

### 3. Invariant tests

Add `tests/integration/test_f00081_invariants.py`:

- **Inv 1** Exactly one `is_default=true` row at all times (queryable assertion).
- **Inv 2** Every `step_runs` row created via the launch helpers has `agent_runtime_option_id IS NOT NULL`.
- **Inv 3** The recorded launch `command` always contains `--model <model>` for `cli_tool ∈ {opencode, claude}`.
- **Inv 4** A bulk PATCH that affects N steps emits exactly one `daemon_events` row (count before and after).
- **Inv 5** Editing an override does not modify any `step_runs` row (compare `step_runs.*` rowset before and after a PATCH).
- **Inv 6** Strip-width budget is a frontend test — covered in S05; if S05 did not cover it, add a TestClient assertion here.

### 4. Audit shape

Add `tests/integration/test_f00081_audit.py`:

- Single-step PATCH → exactly one `daemon_events` row, `event_type='runtime_override_changed'`, metadata payload matches `{item_id, scope:"step", step_ids:[<sid>], old_option_id, new_option_id, actor}`.
- Bulk PATCH affecting 5 steps → one row, `scope:"bulk"`, `step_ids` length == 5.
- Item-level PATCH → one row, `scope:"item"`, `step_ids: null`.

### 5. Coverage gap audit

After running the full suite, produce a brief table in your report:

| AC / Invariant / Boundary row | Test file | Test name |
|---|---|---|
| AC1 | … | … |
| … | … | … |

This makes the verification obvious for S07's cross-agent review.

## Project Conventions

Read `tests/CLAUDE.md`:

- **NEVER** connect tests to live DB on port 5433. Testcontainers only.
- **NEVER** mock the DB in integration tests.
- **MUST** replace psycopg2 URLs with `postgresql+psycopg://` for testcontainers.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- **NEVER** call `importlib.reload(orch.config)`; use `monkeypatch.delenv()`.

## TDD Requirement

These tests describe behaviour that already exists (post S01–S05); S06 is coverage backfill. Run each test against the implementation; if a test reveals a bug, escalate as a blocker — do not silently fix S01–S05 work.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format` → `make typecheck` → `make lint`.

## Test Verification (NON-NEGOTIABLE)

`make test-unit`, `make test-integration`, `make test-frontend` must all pass with no failures introduced.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "tests-impl",
  "work_item": "F-00081",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_f00081_cascade.py",
    "tests/integration/test_f00081_boundaries.py",
    "tests/integration/test_f00081_invariants.py",
    "tests/integration/test_f00081_audit.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": "Coverage table belongs in the report file."
}
```
