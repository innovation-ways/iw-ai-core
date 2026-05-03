# I-00061_S05_CodeReview_Final_prompt

**Work Item**: I-00061 — Auto-skip phantom QV gates at item approval
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01, S03

---

## ⛔ Docker is off-limits

(Standard policy. Read-only `docker ps`/`inspect`/`logs` are allowed.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item adds NO migrations. If any alembic file appears in any step's `files_changed`, that is CRITICAL.)

## Input Files

- **Runtime step state** — `uv run iw item-status I-00061 --json`.
- `ai-dev/active/I-00061/I-00061_Issue_Design.md` — Design (full)
- `ai-dev/active/I-00061/I-00061_Functional.md` — Functional summary
- `ai-dev/active/I-00061/reports/I-00061_S01_Backend_report.md`
- `ai-dev/active/I-00061/reports/I-00061_S02_CodeReview_report.md`
- `ai-dev/active/I-00061/reports/I-00061_S03_Tests_report.md`
- `ai-dev/active/I-00061/reports/I-00061_S04_CodeReview_report.md`
- All files in `files_changed` across S01 and S03

## Output Files

- `ai-dev/active/I-00061/reports/I-00061_S05_CodeReview_Final_report.md` — Final review report

## Context

You are doing the global cross-step review. The implementation (S01) and tests (S03) have each been individually reviewed (S02 / S04). Your job is to verify they compose into a complete, working fix end-to-end — and to catch issues that only appear when looking at the full diff.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
make type-check
```

Any new violations across the union of `files_changed` from S01 and S03 → CRITICAL `conventions`.

## Review Focus — Cross-Step

### 1. End-to-End AC Coverage

Walk through every Acceptance Criterion (AC1-AC5) and trace the call path:

- AC1: phantom Makefile gate → `iw approve` invokes `auto_skip_phantom_qv_gates(trigger="approve")` → calls `classify_qv_gate` → matches `make <target>` pattern → reads Makefile → finds no target → returns `(runnable=False, reason="missing_makefile_target")` → orchestrator sets `step.status = StepStatus.skipped`, inserts `DaemonEvent` → integration test asserts the exact status and metadata → PASS.

If you can't trace the full path for any AC, that is HIGH `architecture`.

### 2. Reproducing Test Validity

The reproducing test (`test_iw_approve_auto_skips_phantom_makefile_gate`) MUST:

- Fail before S01's changes (S03's report should document this).
- Pass on the fix branch.
- Verify SEMANTIC correctness (status enum + event metadata reason), not just response shape.

If S03's report does not document the RED-GREEN check, that is HIGH `testing`.

### 3. Validator Purity Re-check

Now that you can see the full diff together, re-verify:

- `validate_qv_gate` and `classify_qv_gate` have no DB imports, no `Session` parameter, no logging.
- The unit tests do NOT need a database fixture to run — confirm via `make test-unit -k qv_gate_validator` or similar.

### 4. Hook Atomicity

- `iw approve` writes the status transition AND the auto-skip writes inside the SAME transaction (same `with get_session() as session:` block). If they're in different sessions, that is CRITICAL `architecture` — a crash between them would leave an item approved with the daemon picking up phantom gates.
- Same for `iw batch-approve`.

### 5. JSON Output Compatibility

- `iw approve --json` previously returned a dict with at minimum `{project_id, id, status}`. The new output adds `auto_skipped_steps`. Verify nothing downstream breaks: the dashboard's `iw item-status --json` and any test that parses approve output must still work. If `auto_skipped_steps` defaults to `[]` when no skips occurred, that's correct. If it's omitted on no-skip, that's MEDIUM_FIXABLE `code_quality` — always include the key for stable consumers.
- Same compatibility check for `iw batch-approve --json`.

### 6. Conservative-default Invariant

Every code path in `classify_qv_gate` returns `runnable=True` for shapes it cannot confidently classify. Look at the full diff and confirm there is no path that returns `runnable=False` from a catch-all branch. If you find one, CRITICAL `code_quality`.

### 7. Audit Trail Quality

- Every auto-skip emits exactly one `DaemonEvent`. No duplicates, no missing rows.
- Event metadata contains all six keys: `work_item_id`, `step_id`, `gate`, `command`, `reason`, `trigger`.
- `event_type` string is exactly `"step_auto_skipped_phantom_gate"` (no typos, no underscores → dashes drift).
- Verify by reading the integration tests' assertions on `DaemonEvent` rows.

### 8. Scope Compliance

The `workflow-manifest.json` declares `scope.allowed_paths`. The union of `files_changed` from S01 and S03 MUST be a subset of that scope. If any file outside the scope was modified, that is CRITICAL `architecture` — `worktree_commit.sh` will block the merge and the operator will have to amend the scope manually.

### 9. Functional Doc Alignment

Read `I-00061_Functional.md` and confirm the user-facing description matches what the code actually does. If the functional doc says "approving a work item now quietly drops..." but the code prints a noisy summary by default, that's a contradiction — flag MEDIUM_FIXABLE `code_quality`.

### 10. Remaining Risks

Document any risks the reviewer-cycle did not address:

- Edge case: a Feature that *adds* a Makefile target in S01 followed by a QV gate using it in S15 — the validator at approval time would mark S15 phantom. The design doc acknowledges this; verify the test suite does NOT accidentally lock in that as "expected behaviour" (no test should celebrate the false-positive).
- Performance: how many filesystem reads / Makefile reads does `auto_skip_phantom_qv_gates` make for an item with 10 quality_validation steps? If the Makefile is read 10 times instead of once, MEDIUM_FIXABLE `code_quality` — cache the parsed target set per `(repo_root, validator-call)`.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. `make test-unit`
2. `make test-integration`
3. `make lint`
4. `make type-check`

All four must pass.

## Severity Levels

(Standard table.)

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00061",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict`: `pass` iff zero CRITICAL/HIGH/MEDIUM_FIXABLE findings AND all four commands passed.
