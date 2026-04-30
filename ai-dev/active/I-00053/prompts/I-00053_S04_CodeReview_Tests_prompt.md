# I-00053_S04_CodeReview_Tests_prompt

**Work Item**: I-00053 -- Batch Planner Ignores Explicit "Depends on:" / "Blocks:" Declarations
**Step Being Reviewed**: S03
**Review Step**: S04

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/I-00053/I-00053_Issue_Design.md`
- `ai-dev/active/I-00053/reports/I-00053_S03_Tests_report.md`
- `tests/unit/test_design_doc_parser.py`
- `tests/unit/test_batch_planner_dependencies.py`
- `tests/integration/test_register_persists_dependencies.py`

## Output Files

- `ai-dev/active/I-00053/reports/I-00053_S04_CodeReview_report.md`

## Review Checklist

### 1. Coverage of Boundary Behavior table

The design's Boundary Behavior table lists 13 rows. Confirm there is a corresponding parser test for each row that has parser-relevant input. Missing rows are HIGH findings.

- [ ] `Depends on: None` → empty
- [ ] `Depends on: —` → empty
- [ ] `Depends on:` (empty) → empty
- [ ] Comma-separated → list
- [ ] Parenthetical commentary → stripped
- [ ] Dash-separated reason → stripped
- [ ] Section absent → empty
- [ ] Mixed-case heading → recognised
- [ ] Self-dependency (tested at integration level)
- [ ] `Blocks: F-99999` (unregistered) → WARNING
- [ ] Re-register (collision) — confirm test exists OR explicitly note it is left to existing register collision tests
- [ ] Path inside Out of Scope → not extracted
- [ ] Path inside Notes → not extracted
- [ ] Path inside File Manifest → IS extracted (positive control)

### 2. Semantic correctness over shape (CRITICAL — I003 lesson)

For each test, verify that:
- Assertions check SPECIFIC values, not just "key exists" or "list non-empty".
- The test would have FAILED against pre-fix code (i.e. it actually catches the bug).
- The test does not pass for trivially wrong reasons (e.g. `assert X != Y` where `Y` is impossible).

If any test only checks shape, mark CRITICAL and require it to be rewritten with semantic assertions.

### 3. Planner regression tests

- [ ] BATCH-00064 reproduction: F-A in group 0, F-B in group 1, with declared dep.
- [ ] Argument-order independence verified (test runs both orderings).
- [ ] `Blocks` inversion equivalence test — same wave as `Depends on` direct.
- [ ] Out-of-Scope path is NOT extracted.
- [ ] Notes path is NOT extracted.
- [ ] Backwards compatibility test — items with empty deps and no overlap go in group 0.

### 4. Integration tests

- [ ] Use testcontainer fixtures from `tests/integration/conftest.py`, not live DB.
- [ ] Specific value assertions on `WorkItem.depends_on` and `WorkItem.blocks`.
- [ ] `Blocks` inversion test verifies the OTHER item's `depends_on` was mutated.
- [ ] Missing-blocked-target test asserts WARNING was logged.
- [ ] Self-dependency test asserts the self-ID is filtered AND warning logged.

### 5. Live-DB safety

- [ ] No port 5433 connections.
- [ ] No `importlib.reload(orch.config)`.
- [ ] Tests honor `tests/CLAUDE.md`.

### 6. Test quality

- [ ] Test names describe the case (`test_parse_dependencies_section_absent` not `test_1`).
- [ ] Parametrize used where it reduces duplication.
- [ ] Type hints, mypy clean.
- [ ] No flaky timing or network calls.

## Test Verification

- `uv run pytest tests/unit/test_design_doc_parser.py tests/unit/test_batch_planner_dependencies.py -v`
- `uv run pytest tests/integration/test_register_persists_dependencies.py -v`
- `make lint`, `make typecheck`, `make test-unit`, `make test-integration`

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Tests verify shape only; tests pass against pre-fix code; live-DB connection introduced |
| HIGH | Boundary Behavior row uncovered; key invariant unchecked; integration test absent for register |
| MEDIUM (fixable) | Specific assertion missing; helper not reused; `caplog` not used for log assertions |
| MEDIUM (suggestion) | Test could be clearer / DRYer |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00053",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
