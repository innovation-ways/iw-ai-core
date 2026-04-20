# F-00056_S09_Tests_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step**: S09
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- Design document (TDD Approach, all ACs, Invariants, Boundary Behavior)
- `ai-dev/active/F-00056/reports/F-00056_S08_CodeReview_report.md` -- S08 verdict
- All files modified by S01-S07 (see reports `F-00056_S0N_*_report.md` for the full list)
- `tests/CLAUDE.md` -- test organization, testcontainer pattern, FTS setup rules
- `tests/conftest.py` -- existing fixtures

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S09_Tests_report.md` -- Step report

## Context

You are adding comprehensive test coverage for F-00056 and running the backfill on live DB. Earlier steps added minimal tests during TDD; your job is to round out coverage so every AC and Boundary Behavior row has at least one covering test, plus execute the backfill of F-00055 + 2 priors.

## Requirements

### 1. Unit tests (`tests/unit/`)

Create these files with the coverage described:

**`test_execution_report_assembly.py`**
- `ExecutionReportData` correctly assembled for an item with multiple steps, retries, and fix cycles.
- `display_label` fallback chain: step_label → agent_label → opencode_agent → step_id.
- `gantt_class` assignment: retry-color for non-final runs of retried steps; completed-color for final successful; failed-color for terminal failures; in-progress striped for NULL `completed_at`.
- Verdict mapping from `WorkItem.status` (completed, failed, stalled, in_progress, not_started).
- Per-project isolation: an item in project A must not see rows from project B (Invariant 12).
- Boundary: zero StepRun rows → empty timeline, verdict "not_started", no crash.
- Boundary: step with `step_label IS NULL` → falls back correctly.

**`test_execution_report_markdown.py`**
- Output contains all four sections in order (header+verdict, hotspots, timeline, fix cycles) and the footer.
- "No retries — clean run." wording exact for empty hotspot list.
- "_no fix summary captured (pre-F-00056)_" wording exact when `fix_summary IS NULL`.
- Multi-bullet `fix_summary` renders as a multi-line blockquote.
- Renderer is a pure function — same input yields byte-identical output across calls.
- Stdout and file outputs produced from the same input are byte-identical (Invariant 8).

**`test_execution_report_retry_hotspots.py`**
- Detection: only steps with `max(run_number) >= 2` appear.
- Sort order: retry_count desc, then step_number asc (AC6).
- Empty hotspot list for items where every step has `max(run_number) == 1`.

**`test_execution_report_gantt_data.py`**
- Segments generated in `run_number` order per step.
- `gantt_class` rules enforced (Invariant 1, 3).
- Precomputed `StepRunSegment.left_pct` and `width_pct` are floats rounded to 2 decimals; sub-second runs yield `width_pct >= 0.5`.
- Sum of `width_pct` across a step's segments never exceeds 100.0% (Invariant 2); `left_pct + width_pct <= 100.0` for every segment.
- Zero-duration item (no StepRun rows) yields `left_pct == 0.0` and `width_pct == 0.0` without raising.
- `FixCycleEntry.left_pct` / `width_pct` are precomputed and sit between the bounding retry segments on the same step's row.
- QV-gate rows carry the row tint class signal in the shaped data.

**`test_item_report_cli.py`**
- `iw item-report F-00055` writes to `ai-dev/active/F-00055/F-00055_execution_report.md` (or archive path if active absent).
- `--stdout` prints identical markdown to stdout without writing to disk.
- Exit code 0 on success; 1 on unknown item; 2 on path resolution failure.
- `--project` flag respected.
- Use Click's `CliRunner`; do not invoke the actual CLI via subprocess in unit tests.

**`test_fix_summary_ingestion.py`**
- Valid `fix_summary` in agent result JSON is persisted to `FixCycle.fix_summary` (integration with testcontainer, or unit with an in-memory DB if the ingestion function is pure).
- Missing key → NULL (not empty string).
- Empty string → NULL.
- Multi-paragraph over 20000 chars → truncated at 20000 (safety cap). Contents up to 20000 chars (including typical 2000-char responses) are stored verbatim without truncation.
- Malformed JSON payload → NULL, no exception raised, warning logged.

### 2. Integration tests (`tests/integration/`)

Create these files. Use the PostgreSQL testcontainer fixture per `tests/CLAUDE.md`. After `Base.metadata.create_all()`, run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` (critical per project CLAUDE.md). Replace psycopg2 URLs with psycopg v3 strings as specified.

**`test_execution_report_auto_generation.py`**
- Seed a work item with multiple steps, three StepRuns on one step (mimicking F-00055's S13 lint 3x) and two fix cycles with non-NULL `fix_summary` values.
- Seed another step with two StepRuns and one fix cycle with NULL `fix_summary`.
- Call the daemon's `_complete_item()` hook (or its extracted wrapper).
- Assert: markdown file written to the expected path with the expected content signatures (header, hotspot bullets, the "_no fix summary captured_" placeholder for the NULL case).
- Assert: auto-generation failure logs a warning but does not roll back the completion transition.

**`test_execution_report_dashboard_route.py`**
- Seed the same item.
- Using FastAPI `TestClient`, GET both `/project/{pid}/item/{iid}/tab/execution-report` and `/project/{pid}/item/{iid}/execution-report`.
- Assert HTTP 200 for both; assert key HTML selectors exist: summary card container, hotspot `<ul>`, Gantt rows (count == number of WorkflowStep rows), timeline `<details>` elements for hotspot steps.
- Assert HTTP 404 for a non-existent `work_item_id`.
- Assert that the existing tabs (Overview, Design Doc, Reports, Artifacts, Evidences, Logs, Fix Cycles) still return HTTP 200 and their HTML body length/hash is unchanged vs a snapshot taken at the start of the test (Invariant 7, snapshot approach). Implement this as a separate test case `test_existing_tabs_byte_identical`.

### 3. Execute the backfill on live DB

After all tests pass locally, run the backfill:

```bash
uv run iw item-report F-00055 --project iw-ai-core
```

Then identify the two work items completed most recently before F-00055 (query `WorkItem.completed_at` in `iw-ai-core`, descending, offset 1-2) and run:

```bash
uv run iw item-report <id_1> --project iw-ai-core
uv run iw item-report <id_2> --project iw-ai-core
```

**Path resolution is dynamic.** `resolve_report_path()` (from S03) writes to:
1. `ai-dev/active/<id>/<id>_execution_report.md` if the active dir exists, else
2. `ai-dev/archive/<id>/<id>_execution_report.md` if the archive dir exists, else
3. the CLI exits with code 2.

Some of the three backfilled items may already be archived by the time this step runs — the CLI will pick the correct directory per item. After each invocation, parse the CLI's stdout (it prints the written path) OR `git status` to learn the actual path chosen, and use those exact paths in the `files_changed` list below (NOT the template `ai-dev/active/<id>/...` placeholders).

Verify each of the three generated files exists at its resolver-determined path and is non-empty. Commit the generated files as part of this step. Include the absolute item IDs (`<id_1>`, `<id_2>`) **and their resolved file paths** in the step report's `notes` field so reviewers know which items were backfilled and where each report landed (active vs archive).

Note on environment: this backfill runs inside the F-00056 worktree but writes touch `ai-dev/active/<other-id>/` or `ai-dev/archive/<other-id>/` — directories that belong to other work items. The resulting commit therefore adds files outside F-00056's own directory; that's expected. The daemon's standard DB connection is used (port 5433 per `.env`); no test-container DB is used for backfill because backfill must read real historical rows.

### 4. Do not duplicate earlier tests

S01, S03, S05, and S07 wrote minimal tests as part of TDD. Do not delete those, but do not duplicate them either. Your coverage extends theirs; where you find a test that S03 already wrote, either leave it alone or refactor it into a more comprehensive one (mark the refactor in the step report).

### 5. Test isolation and conventions

- NEVER connect tests to the live DB (port 5433) — use testcontainers only.
- NEVER call `importlib.reload(orch.config)`; use `monkeypatch.delenv()` instead.
- NEVER mock the database in integration tests — FOR UPDATE locking can't be tested otherwise.
- MUST replace psycopg2 URLs in testcontainers: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- MUST run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.

Deviations from these will fail the review.

## Project Conventions

Read `tests/CLAUDE.md` for fixture naming, marker usage, and file organization.

## TDD Requirement

All tests in this step are written first (the implementation they test already exists from S01-S07, but the test-first discipline still applies inside this step: write the test, run it red, run it green). Add edge cases you discover while writing.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all new unit tests pass; no existing tests regress
2. `make test-integration` — all new integration tests pass; no existing tests regress
3. `uv run ruff check tests/`
4. `uv run mypy tests/` (if the project runs mypy on tests; otherwise skip)
5. Backfill commands executed and three markdown files present on disk

Do not report `tests_passed: true` unless all five conditions are met.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "tests-impl",
  "work_item": "F-00056",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_execution_report_assembly.py",
    "tests/unit/test_execution_report_markdown.py",
    "tests/unit/test_execution_report_retry_hotspots.py",
    "tests/unit/test_execution_report_gantt_data.py",
    "tests/unit/test_item_report_cli.py",
    "tests/unit/test_fix_summary_ingestion.py",
    "tests/integration/test_execution_report_auto_generation.py",
    "tests/integration/test_execution_report_dashboard_route.py",
    "<resolved path for F-00055 — active/ or archive/>",
    "<resolved path for <id_1>>",
    "<resolved path for <id_2>>"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (unit), Y passed, 0 failed (integration)",
  "blockers": [],
  "notes": "Backfilled items and resolved paths: F-00055 → <path>, <id_1> → <path>, <id_2> → <path>"
}
```
