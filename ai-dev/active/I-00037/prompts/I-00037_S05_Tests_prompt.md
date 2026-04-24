# I-00037_S05_Tests_prompt

**Work Item**: I-00037 -- Per-project dashboard still uses item-level batch progress after I-00036
**Step**: S05
**Agent**: Tests

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker state. Allowed:
testcontainers spun up by pytest fixtures (they self-destruct via Ryuk).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations expected. Testcontainer fixtures run
`Base.metadata.create_all()` + `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` per
`tests/CLAUDE.md`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00037/I-00037_Issue_Design.md` -- Design document
- `ai-dev/active/I-00037/reports/I-00037_S01_Backend_report.md`
- `ai-dev/active/I-00037/reports/I-00037_S02_CodeReview_report.md`
- `ai-dev/active/I-00037/reports/I-00037_S03_Frontend_report.md`
- `ai-dev/active/I-00037/reports/I-00037_S04_CodeReview_report.md`
- `dashboard/utils/batch_progress.py` -- Shared helper
- `dashboard/routers/project_dashboard.py` -- `_active_batches()` (fixed)
- `dashboard/routers/batches.py` -- `_all_batches()` (refactored to use helper)
- `tests/CLAUDE.md`, `tests/conftest.py` -- Testing rules and fixtures

## Output Files

- `tests/dashboard/test_batches_progress_parity.py` (or canonical path you choose — see Requirement 1)
- `ai-dev/active/I-00037/reports/I-00037_S05_Tests_report.md` -- Step report

## Context

You are adding automated tests that:

1. **Reproduce** the bug — would have FAILED against the pre-S03 code (where
   `_active_batches()` returned item-based progress, e.g., `0` for a partially
   completed batch).
2. **Lock the parity** between `_active_batches()` and `_all_batches()` so the
   two views cannot drift again.
3. **Regress-protect** the helper against every status-classification edge
   called out in the design doc.

The fix lives in three places: the new helper at
`dashboard/utils/batch_progress.py` (pure function — best target for unit
tests), plus the two router wirings in `project_dashboard.py` and
`batches.py` (best targets for integration tests).

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty)
and passed. But the bug was NOT fixed. Tests must verify **SPECIFIC VALUES**:

- BAD: `assert "progress_pct" in data` (shape only)
- BAD: `assert row.progress_pct >= 0` (non-semantic — passes even for a 0% bug)
- GOOD: `assert row.progress_pct == 30` (semantic — specific expected value)
- GOOD: `assert dash.progress_pct == full.progress_pct` (semantic — parity
  assertion: the two routers MUST agree, no matter what value)
- GOOD: `assert dash.progress_pct != 0 and dash.progress_pct != 100` (semantic
  — excludes the item-based bug's signature output)
- GOOD: `assert dash.completed_items == 0` (semantic — confirms Items column
  stayed item-based, not accidentally switched)

Every assertion MUST pin a specific expected value derived from the scenario
setup. If you catch yourself writing `>= 0`, `is not None`, or `len(x) > 0`
as the only assertion for a value, escalate it to a real expected integer.

## Requirements

### 1. Find or create the canonical test module

Look under `tests/dashboard/` for an existing `test_batches*.py` module. If
I-00036 created `tests/dashboard/test_batches_progress.py`, extend it so
related tests cluster together. If not, create
`tests/dashboard/test_batches_progress_parity.py`.

Follow `tests/conftest.py` fixture conventions:

- Use the testcontainer-backed `db_session` fixture for DB-backed tests.
- Use whatever `TestClient` / app fixture exists for HTTP-level smoke tests.
- NEVER hit the live DB (port 5433). NEVER mock the DB.
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `create_all()` if the
  existing fixture doesn't already do it.
- Swap psycopg2 URL prefix: `postgresql+psycopg2://` → `postgresql+psycopg://`.

### 2. Reproduction + parity test (MANDATORY)

Name: `test_I00037_dashboard_home_and_batches_view_agree_on_progress`.

Scenario (from design doc Test to Reproduce):

- One work item with 10 `WorkflowStep` rows.
- Steps 1..3 status = `StepStatus.completed`; steps 4..10 = `StepStatus.pending`.
- One batch with one `BatchItem` (`BatchItemStatus.in_progress`) for the work
  item.

Actions:

- Call `_active_batches(project_id, db_session)` → `dashboard_rows`.
- Call `_all_batches(project_id, db_session, status_filter=[])` → `batches_rows`.

Assertions (all semantic):

- `dash.progress_pct == 30`
- `full.progress_pct == 30`
- `dash.progress_pct == full.progress_pct`  ← **PARITY LOCK**
- `dash.completed_items == 0`  (Items column stays item-level)
- `dash.total_items == 1`
- `full.completed_items == 0`
- `full.total_items == 1`

This test MUST fail against the pre-S03 `project_dashboard.py` (it would
return `dash.progress_pct == 0`). Confirm by inspecting the current code
before writing the test — the test is the proof of the bug.

### 3. Regression test set — helper directly

Test the helper in isolation (`compute_batch_step_progress`) for the edge
matrix. One test per scenario; each asserts a specific expected value.

| Test | Scenario | Expected |
|------|----------|----------|
| `test_helper_empty_batch_ids_returns_empty_dict` | `batch_ids=[]` | `{}` (and no query executed if possible to observe) |
| `test_helper_single_batch_3_of_10_done` | 1 item, 10 steps, 3 completed | `{batch.id: 30}` |
| `test_helper_all_steps_done_is_100` | 1 item, 5 steps, all completed | `{batch.id: 100}` |
| `test_helper_zero_steps_is_0_not_crash` | 1 item, 0 WorkflowStep rows | `{batch.id: 0}` (no divide-by-zero) |
| `test_helper_skipped_counts_as_done` | 1 item, 10 steps: 2 completed + 2 skipped + 6 pending | `{batch.id: 40}` |
| `test_helper_failed_does_not_count` | 1 item, 10 steps: 3 completed + 2 failed + 5 pending | `{batch.id: 30}` (NOT 50) |
| `test_helper_needs_fix_does_not_count` | 1 item, 10 steps: 3 completed + 1 needs_fix + 6 pending | `{batch.id: 30}` (NOT 40) |
| `test_helper_in_progress_does_not_count` | 1 item, 10 steps: 3 completed + 1 in_progress + 6 pending | `{batch.id: 30}` |
| `test_helper_multi_batch_bulk` | Batches {A: 1/10, B: 5/10, C: 0 steps, D: 10/10} asked in one call | `{A:10, B:50, C:0, D:100}` |
| `test_helper_missing_batch_id_defaults_to_0` | Ask for `batch_ids=[existing_id, "BATCH-DOESNOTEXIST"]` | nonexistent key maps to `0`, no KeyError |
| `test_helper_scopes_by_project_id` | Two projects with same-named `work_item_id`s; ask for project A's batch | counts reflect ONLY project A's steps (critical regression guard) |

### 4. Regression test set — via the routers

Mirror the most important scenarios end-to-end so a future router refactor
can't route around the helper:

- `test_active_batches_and_all_batches_match_on_partial` — same seeded state,
  both routers return the SAME `progress_pct`.
- `test_active_batches_total_items_is_item_count_not_step_count` —
  `BatchSummary.total_items == 1` when there's 1 item even though there are 10
  steps.

### 5. HTTP smoke test (TestClient)

ONE test each for the two routes, on the same seeded state (3-of-10 scenario):

- `GET /project/{project_id}/` — assert the rendered HTML contains `30%` (or
  `30% complete`) in the Active Batches card area.
- `GET /project/{project_id}/batches` — assert the rendered HTML contains the
  same `30%` in the Progress column.

Keep these narrow — the math assertions already live in the unit tests. The
smoke test's only job is to confirm the value flows into the template.

### 6. DO NOT

- Do NOT write tests that only check response shape (`"progress" in html`,
  `isinstance(row.progress_pct, int)`, `assert rows`).
- Do NOT edit `dashboard/utils/batch_progress.py` or either router — if a
  test surfaces a bug, raise a blocker instead of patching (the fix cycle
  will route it back to S01 or S03).
- Do NOT mock the DB.

## Project Conventions

Read `tests/CLAUDE.md` for:

- testcontainer fixtures
- FTS SQL application rule (`FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after
  `create_all()`)
- `postgresql+psycopg2://` → `postgresql+psycopg://` URL swap
- Never mock the DB

Read `tests/conftest.py` to find the existing fixtures and use them (not new
ones).

## Test Verification (NON-NEGOTIABLE)

After writing tests:

1. Run your new test file: `uv run pytest tests/dashboard/<module>.py -v`
2. `make test-unit` — no regressions.
3. `make test-integration` — no regressions.
4. Report results accurately.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "Tests",
  "work_item": "I-00037",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_batches_progress_parity.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (new tests + full suite)",
  "blockers": [],
  "notes": "Confirm: (a) canonical test file path, (b) parity assertion present, (c) every assertion pins a specific expected value (list 1-2 scenarios where you explicitly avoided shape-only), (d) project_id scoping regression test included."
}
```
