# I-00075_S05_CodeReview_Final_prompt

**Work Item**: I-00075 -- Add E2E seed fixture with `fix_cycle_count >= 1` for browser verification of fix-cycle amber pills
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

(Standard policy — see I-00075_S02_CodeReview_Backend_prompt.md for the full text.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.) No migration is in scope for I-00075. If any file under `orch/db/migrations/versions/**` was added or modified across S01..S04, that is a CRITICAL out-of-scope finding.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00075 --json`
- `ai-dev/active/I-00075/I-00075_Issue_Design.md` -- Design document
- `ai-dev/active/I-00075/I-00075_Functional.md` -- Functional design
- `ai-dev/active/I-00075/reports/I-00075_S01_Backend_report.md`
- `ai-dev/active/I-00075/reports/I-00075_S02_CodeReview_report.md`
- `ai-dev/active/I-00075/reports/I-00075_S03_Tests_report.md`
- `ai-dev/active/I-00075/reports/I-00075_S04_CodeReview_report.md`
- `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py`
- `tests/integration/test_i00075_fix_cycle_fixture.py`

## Output Files

- `ai-dev/active/I-00075/reports/I-00075_S05_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the final cross-agent review of I-00075. Per-agent reviews (S02, S04) have already validated their own steps. Your job is to catch issues that span both the fixture and the test together.

The work surface is small — two files. Focus on:

1. **Completeness vs. design** — every requirement in the design doc has corresponding code or test assertion.
2. **Cross-step consistency** — the test's assertions match the fixture's actual data shape (no off-by-one between what the fixture seeds and what the test counts).
3. **Integration of `_run_fixture`** — the test exercises the same loader path the daemon uses (`scripts.e2e_seed._run_fixture` is also called by `scripts/e2e_apply_item_fixtures.py:_run_fixture` import).
4. **Acceptance Criteria coverage** — AC1, AC2, AC3 each map to at least one test assertion or the qv-browser script.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any NEW violation in either of the two changed files (vs. `main`) is a **CRITICAL** finding with `category: "conventions"`.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs Design Document

For every requirement in `I-00075_Issue_Design.md` § Requirements (S01) and § TDD Approach (S03), verify a corresponding implementation exists:

- [ ] Fixture file exists at the design-specified path with the design-specified `001_` prefix
- [ ] All 4 mandated test functions exist
- [ ] AC1 (amber pill renders) — covered by qv-browser S13 (validate the prompt is consistent with the fixture)
- [ ] AC2 (regression test exists) — covered by `test_i00075_fixture_*` suite
- [ ] AC3 (no regression on zero-cycle items) — covered by qv-browser S13 V2 (validate the prompt mentions visiting a non-fixture item)

### 2. Cross-Step Consistency — fixture vs. test

This is the highest-value cross-cutting check. Verify the test assertions match the fixture's actual data shape:

- [ ] Test asserts exactly 2 FixCycle rows AND fixture writes exactly 2 FixCycle rows
- [ ] Test asserts cycle attachment to `S02` AND fixture writes the FixCycles against the WorkflowStep with `step_id == "S02"`
- [ ] Test asserts 3 WorkflowStep rows AND fixture writes exactly 3 WorkflowStep rows
- [ ] Test asserts step_types `[implementation, code_review, quality_validation]` AND fixture writes the same enum values in the same step_number order
- [ ] Test asserts `WorkItem.id == "I-99001"` AND fixture writes `WorkItem.id="I-99001"` (constant must match exactly)

Any mismatch is a CRITICAL finding with `cross_cutting: true`.

### 3. Integration Points

- [ ] Fixture's idempotency guard checks `WorkflowStep` (not `WorkItem`) — verify and confirm this is correct because re-running the fixture on a session that already has the WorkItem but lost the WorkflowStep would otherwise re-insert child rows. (Discuss in your finding if you disagree with the chosen guard.)
- [ ] Test's `_run_fixture` import path matches the production loader: `from scripts.e2e_seed import _run_fixture`.
- [ ] No `db.commit()` in either file — the caller owns transaction lifecycle.
- [ ] Composite-PK convention `(project_id, id)` is preserved in every `db.get(WorkItem, ...)` lookup.

### 4. Test Coverage (Holistic)

- [ ] Happy path covered (file present, fixture loads, rows seeded)
- [ ] Idempotency covered (second run is no-op)
- [ ] Negative space NOT under-tested: verify a test asserts the wrong-data shape would fail (this is implicit in the exact-count assertions S04 should have validated; double-check)

### 5. Architecture Compliance

- [ ] Read `CLAUDE.md` and `orch/CLAUDE.md`
- [ ] Fixture lives outside `orch/` and `dashboard/` layers (it's test-data, not production)
- [ ] No new circular dependencies introduced
- [ ] Append-only convention respected: no `UPDATE` to step_runs/fix_cycles/daemon_events

### 6. Security

- [ ] No hardcoded secrets, tokens, or PII in either file
- [ ] Both files write only to `project_id="iw-ai-core"` — confirm by grepping for any other project_id literal

### 7. Out-of-scope changes

Per `workflow-manifest.json:scope.allowed_paths`, the merged change set MUST include exactly:

- `ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py`
- `tests/integration/test_i00075_fix_cycle_fixture.py`

(Plus the design-time `ai-dev/active/I-00075/**` files which are implicitly allowed.) Any other production-code or test file in the diff is a CRITICAL `cross_cutting: true` finding.

## Test Verification (NON-NEGOTIABLE)

Before submitting:

```bash
uv run pytest tests/integration/test_i00075_fix_cycle_fixture.py -v
make test-unit
```

Run the **full unit suite** (cheap; ~30s) to verify no unrelated regressions, plus the targeted I-00075 integration test. **Do NOT** run `make test-integration` here — that is the S12 QV gate's job.

If integration tests fail or unit tests regress, that is a CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Cross-step shape mismatch, out-of-scope file in diff, broken test, missing AC coverage | Must fix before merge |
| **HIGH** | Idempotency drift, integration point miswired, design doc requirement uncovered | Must fix before merge |
| **MEDIUM (fixable)** | Convention violation, missing assertion message, lint warning | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better helper placement, naming preference | Optional |
| **LOW** | Nitpicks | Informational only |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00075",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "4 integration + N unit passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
