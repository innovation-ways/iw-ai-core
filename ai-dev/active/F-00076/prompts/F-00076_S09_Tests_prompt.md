# F-00076_S09_Tests_prompt

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S09
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Same constraints as the design document.)

## Input Files

- `uv run iw item-status F-00076 --json`
- `ai-dev/active/F-00076/F-00076_Feature_Design.md` (sections: Acceptance Criteria, Boundary Behavior, Invariants, TDD Approach)
- `ai-dev/active/F-00076/reports/F-00076_S0{1,3,4,7}_*_report.md`
- All implementation files from S01–S07

## Output Files

- `ai-dev/active/F-00076/reports/F-00076_S09_Tests_report.md`
- Additional tests beyond what each implementation step shipped

## Context

S01–S07 each shipped tests covering their layer. This step fills coverage gaps for cross-cutting cases that no single layer owns. Read all S01–S07 reports first to inventory existing coverage; then add ONLY missing cases.

## Requirements

### 1. Coverage gap analysis

Open each `S0{1,3,4,7}_*_report.md` and list the test files added. Cross-reference against the design's "Boundary Behavior" table — every row must map to at least one test. Flag any uncovered rows.

### 2. End-to-end integration test

`tests/integration/test_f_00076_e2e.py` — a single test that:

- Seeds two Feature `WorkItem` rows with overlapping `impacted_paths`.
- Creates two batches A and B, approves both.
- Drives the daemon's `_process_batch` for each batch (use the existing daemon fixtures).
- Asserts only one item launches per project per cycle when overlap exists.
- Transitions the first item through `executing` → `merging` → `merged`.
- Asserts the held item launches in the next poll cycle.

### 3. Negative tests

- `tests/integration/test_f_00076_research_bypass.py` — Feature in flight + Research candidate with overlapping globs → Research launches. Use the `WorkItemType.research` value.
- `tests/integration/test_f_00076_cross_project_no_block.py` — two items with identical paths in DIFFERENT projects → both launch (project filter works).
- `tests/integration/test_f_00076_test_globs_ignored.py` — items overlap ONLY on `**/tests/**` → both launch.

### 4. Held-event cadence test

`tests/integration/test_f_00076_held_event_cadence.py`:

- Seed a Feature in `executing` and a candidate Feature with overlapping globs.
- Run `_process_batch` 3 times.
- Assert exactly 3 `item_held_for_scope` events emitted (one per cycle), each with the same payload.

### 5. Scope extraction provenance round-trip test

`tests/integration/test_f_00076_scope_extraction_round_trip.py`:

- For each combination of (declared / regex_fallback / none), register a Feature, query `config["scope_extraction"]` from the DB, and assert exact match against the design contract (AC3/AC4).

### 6. Backfill idempotency

If S01's migration test doesn't already cover this, add `tests/integration/db/test_impacted_paths_backfill_idempotent.py`:

- Run the migration twice (downgrade → upgrade → downgrade → upgrade).
- Assert `impacted_paths` is identical after both runs.
- Assert no duplicate rows or other corruption.

### 7. Performance smoke test

`tests/integration/test_f_00076_gate_performance.py`:

- Seed 50 in-flight items (random globs from a fixed set).
- Time the cross-batch gate evaluation for one new candidate.
- Assert under 100ms — fail with a useful message if the probe-based intersection is too slow at this scale.

## Project Conventions

`tests/CLAUDE.md` — testcontainer rules, FTS triggers, no `importlib.reload`, psycopg URL replacement.

## TDD Requirement

Tests added in this step are NEW — they may RED initially because the implementation might miss an edge case. Report any genuine RED tests as blockers; do NOT modify implementation code in this step (return to S04/S07 if changes are needed).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

1. `make test-unit`
2. `make test-integration` — full suite must pass.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "tests-impl",
  "work_item": "F-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_f_00076_e2e.py",
    "tests/integration/test_f_00076_research_bypass.py",
    "tests/integration/test_f_00076_cross_project_no_block.py",
    "tests/integration/test_f_00076_test_globs_ignored.py",
    "tests/integration/test_f_00076_held_event_cadence.py",
    "tests/integration/test_f_00076_scope_extraction_round_trip.py",
    "tests/integration/db/test_impacted_paths_backfill_idempotent.py",
    "tests/integration/test_f_00076_gate_performance.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
