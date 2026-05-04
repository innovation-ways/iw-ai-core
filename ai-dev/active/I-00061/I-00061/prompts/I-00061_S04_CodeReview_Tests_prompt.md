# I-00061_S04_CodeReview_Tests_prompt

**Work Item**: I-00061 — Auto-skip phantom QV gates at item approval
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures are exempt; nothing else here touches Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. S03 must NOT have added or modified any alembic file. If it did, that is CRITICAL.)

## Input Files

- `ai-dev/active/I-00061/I-00061_Issue_Design.md` — Design (especially AC1-AC5)
- `ai-dev/active/I-00061/reports/I-00061_S03_Tests_report.md` — S03 report
- `tests/unit/test_qv_gate_validator.py` (new)
- `tests/integration/test_phantom_gate_auto_skip.py` (new)
- S01's source files for cross-reference: `orch/qv_gate_validator.py`, `orch/cli/item_commands.py`, `orch/cli/batch_commands.py`
- `tests/CLAUDE.md` — testing conventions
- `tests/conftest.py` — fixture inventory

## Output Files

- `ai-dev/active/I-00061/reports/I-00061_S04_CodeReview_report.md` — Review report

## Context

You are reviewing the test suite written in S03. The implementation in S01 is already reviewed (S02). Your job is to verify the tests cover every Acceptance Criterion semantically, run for real, and lock in the regression.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violations in `tests_changed` files → CRITICAL `conventions`.

## Review Checklist

### 1. AC Coverage

Map each acceptance criterion in the design doc to one or more test cases. Every AC must have ≥1 test that covers it semantically.

| AC | Test |
|----|------|
| AC1 (phantom Makefile auto-skipped at approve) | `test_iw_approve_auto_skips_phantom_makefile_gate` (or equivalent) |
| AC2 (phantom `cd dir` auto-skipped at approve) | `test_iw_approve_auto_skips_phantom_cd_gate` |
| AC3 (real gates NOT skipped) | `test_iw_approve_does_not_skip_real_gates` |
| AC4 (batch-approve safety net) | `test_iw_batch_approve_runs_safety_net` |
| AC5 (regression test exists) | The whole file's existence and passing run |

If any AC has no test, that is HIGH `testing`.

### 2. Semantic Correctness

For every assertion, check that it verifies a SPECIFIC value, not just shape. Examples of MUST-FAIL findings:

| Assertion in test | Verdict |
|-------------------|---------|
| `assert "auto_skipped_steps" in out` | CRITICAL `testing` — shape only |
| `assert len(skipped) > 0` | CRITICAL `testing` — non-empty only |
| `assert step.status != StepStatus.pending` | HIGH `testing` — not specific |
| `assert step.status == StepStatus.skipped` | OK |
| `assert ev.event_metadata["reason"] == "missing_directory"` | OK |

If a test asserts the SHAPE of a response without verifying the SEMANTIC content, classify as CRITICAL `testing`. Refer to the I003 lesson explicitly in your finding description.

### 3. Real-fixture Honesty

- The integration tests MUST hit a real PostgreSQL testcontainer. Search the test files for `Mock`, `patch`, `MagicMock`, `monkeypatch.setattr.*qv_gate_validator` — if any of those replace `validate_qv_gate`, `classify_qv_gate`, `auto_skip_phantom_qv_gates`, or any DB function with a stub, that is CRITICAL `testing`.
- The unit tests can use `tmp_path` (filesystem) but MUST NOT mock the validator under test. They use real `Path` operations and a real `shutil.which`. If a test mocks `shutil.which`, that's HIGH unless there's a strong reason (e.g., portability across CI envs).

### 4. RED-GREEN Verification

The S03 report should document a RED-GREEN check on the reproducing test (run on `main` → fails; run on the fix branch → passes). If the report doesn't mention this OR doesn't quote the failing test output from the RED phase, that is HIGH `testing` — without RED-GREEN we have no evidence the test actually catches the bug.

### 5. Test Isolation

- Each test must set up its own state (its own work item, its own Makefile content). No test should depend on another test's side effects.
- Each test should clean up via the testcontainer rollback or fixture teardown — not by hand-deleting rows.
- If two tests share an item ID like `I-99001`, they must run in fully isolated transactions / containers. Otherwise it's HIGH `testing`.

### 6. Edge Case Coverage

Confirm tests for:

- [ ] `make` with no Makefile at all (validator must not crash).
- [ ] `cd <dir>` where `<dir>` is a regular file, not a directory.
- [ ] Bare-exec phantom (binary not on PATH).
- [ ] Conservative-default cases (unknown shell pipeline, `make` with no target, env-var prefix) — MUST return runnable.
- [ ] Empty `quality_validation` list on an item (validator must be a no-op, exit 0).
- [ ] Item with mixed real and phantom gates (only phantom ones skipped).
- [ ] Batch with multiple items, each with mixed gates.

Missing any of these is HIGH `testing` if it maps to a real branch in the validator code.

### 7. Project Conventions (`tests/CLAUDE.md`)

- psycopg URL replaced (no `psycopg2` survives in the testcontainer URL).
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` run after `Base.metadata.create_all()` — confirm the fixture used by integration tests does this.
- No `importlib.reload(orch.config)` anywhere.

### 8. Test Names and Documentation

Test names must clearly describe what they verify. `test_validator_works` is bad; `test_makefile_target_present_returns_runnable` is good. Flag any vague names as MEDIUM_FIXABLE `conventions`.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. `make test-unit` — must pass cleanly.
2. `make test-integration` — must pass cleanly.

Report any flakes (a test that passed once and failed once across a small number of runs) as HIGH `testing`.

## Severity Levels

(Standard table.)

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00061",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict`: `pass` iff zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
