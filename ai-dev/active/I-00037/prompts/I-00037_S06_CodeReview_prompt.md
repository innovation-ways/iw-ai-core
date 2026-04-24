# I-00037_S06_CodeReview_prompt

**Work Item**: I-00037 -- Per-project dashboard still uses item-level batch progress after I-00036
**Step Being Reviewed**: S05 (Tests)
**Review Step**: S06

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker state.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations expected.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00037/I-00037_Issue_Design.md` -- Design document (check regression matrix)
- `ai-dev/active/I-00037/reports/I-00037_S05_Tests_report.md` -- S05 report
- Files listed in S05's `files_changed` (the new/extended test module)

## Output Files

- `ai-dev/active/I-00037/reports/I-00037_S06_CodeReview_report.md`

## Context

S05 added reproduction + parity + regression tests. You are verifying the
test suite is **semantically correct** (pins specific values, not shapes),
**covers the design doc's regression matrix**, and **would actually catch
the bug** if the fix were reverted.

## Review Checklist

### 1. The reproduction test actually reproduces the bug (CRITICAL-class)

- [ ] Locate `test_I00037_dashboard_home_and_batches_view_agree_on_progress`
  (or the test the Tests agent named for the design-doc Test to Reproduce
  scenario).
- [ ] Mentally revert the fix: imagine `project_dashboard.py:_active_batches()`
  still computes `pct = int(done_items / total_items * 100)`. With 1 `BatchItem`
  in status `in_progress`, `done_items == 0`, so `progress_pct` would be `0`,
  not `30`. The test MUST fail in that scenario. If it would still pass
  because of weak assertions → **CRITICAL**.
- [ ] The scenario matches the design doc exactly: **1 item, 10 `WorkflowStep`
  rows, 3 completed, 7 pending, 1 `BatchItem` with status `in_progress`**.
- [ ] Assertions pin `progress_pct == 30` on BOTH routers AND assert parity
  (`dash.progress_pct == full.progress_pct`). All three conditions must be
  present — the parity assertion is the lock against future drift.

### 2. Semantic correctness in every assertion (HIGH-class)

Scan every `assert` in the test file. Flag **HIGH** for any of:

- `assert "progress_pct" in <thing>` (shape only)
- `assert <value> >= 0` / `<= 100` (non-semantic)
- `assert isinstance(<x>, int)` (type-only)
- `assert len(rows) > 0` (shape only)
- `assert "%" in html` (too loose; passes for `0%`)

Each `progress_pct` assertion must pin a specific integer derived from the
scenario's step counts. HTML smoke-test assertions must match a substring
unique to the correct percentage (e.g., `"30%"`, not `"%"`).

### 3. Regression matrix coverage (HIGH-class)

Confirm these scenarios are present (one test each or tightly parametrised):

- [ ] empty `batch_ids` → `{}`
- [ ] 3/10 done → 30
- [ ] all done → 100
- [ ] 0 steps → 0 (no crash)
- [ ] `skipped` counts as done (→ 40 for 2 completed + 2 skipped out of 10)
- [ ] `failed` does NOT count (→ 30 for 3 completed + 2 failed out of 10)
- [ ] `needs_fix` does NOT count (→ 30 for 3 completed + 1 needs_fix out of 10)
- [ ] `in_progress` does NOT count
- [ ] multi-batch bulk call returns correct dict
- [ ] missing batch_id → 0 (no `KeyError`)
- [ ] `project_id` scoping — same `work_item_id` in another project does NOT leak

Missing any of these → **HIGH**, fixable in the fix cycle.

### 4. Parity test present

- [ ] At least one test explicitly calls both `_active_batches()` and
  `_all_batches()` with the same seeded state and asserts
  `dash.progress_pct == full.progress_pct`. Without this, a future router
  refactor could split the two views again.

### 5. Items-count preservation

- [ ] At least one assertion confirms `BatchSummary.total_items == 1` when
  there's 1 item and 10 steps — proving Items stayed item-based per the
  reporting user's explicit instruction.

### 6. Test isolation & project conventions

- [ ] No test hits port 5433 (live DB). All use testcontainer-backed
  `db_session`.
- [ ] No test mocks the DB.
- [ ] If the fixture is new, it runs `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`
  after `create_all()` (or reuses a fixture that does).
- [ ] psycopg URL swap applied if the test creates its own engine.
- [ ] Tests are deterministic (no reliance on wall-clock times, DB insertion
  order, etc.).

### 7. HTTP smoke test

- [ ] One test hits `GET /project/{id}/` and asserts "30%" (or the exact
  expected rendered percentage) appears in the Active Batches card.
- [ ] One test hits `GET /project/{id}/batches` and asserts the same
  percentage appears.

Both being present is a **prove-it-ships** layer — the unit tests assert the
math, these prove the math reaches the template.

## Test Verification (NON-NEGOTIABLE)

1. Run the new test file: `uv run pytest tests/dashboard/<S05's_module>.py -v`
2. `make test-unit` + `make test-integration` — no regressions.
3. `make lint` and `make typecheck` — baseline passes.

## Severity Levels

| Severity | Use when |
|----------|----------|
| CRITICAL | Reproduction test would pass against pre-fix code; missing parity assertion; `progress_pct` never pinned to a specific integer anywhere |
| HIGH | Missing regression scenarios from the matrix; shape-only assertions as the sole check for a progress value; test hits live DB or mocks DB |
| MEDIUM (fixable) | Test relies on fixture state set up elsewhere without guarding; missing test for one matrix entry |
| MEDIUM (suggestion) | Parametrise repetitive tests; better naming |
| LOW | Nitpicks |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00037",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "testing|correctness|conventions",
      "file": "",
      "line": 0,
      "description": "",
      "suggestion": ""
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
