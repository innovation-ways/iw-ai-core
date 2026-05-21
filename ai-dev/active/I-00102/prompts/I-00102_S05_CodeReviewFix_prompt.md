# I-00102_S05_CodeReviewFix_prompt

**Work Item**: I-00102 — iw register silently ignores design-package drift; approve must auto-refresh workflow_steps
**Fixing Findings From**: S04 (code-review-impl)
**Step**: S05
**Agent**: code-review-fix-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

If you must adjust the alembic migration (e.g. column placement or naming feedback), edit the existing revision file in place — do NOT add a second migration on top. If S08 (`make migration-check`) catches a drift after your edit, that is a true RED you must fix.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00102 --json`.
- `ai-dev/active/I-00102/reports/I-00102_S04_CodeReview_report.md` — the findings list.
- `ai-dev/active/I-00102/I-00102_Issue_Design.md` — the acceptance contract (your fixes must keep AC1–AC5 satisfied).
- All files touched in S01/S02/S03.

## Output Files

- Edits to the production files touched in S01/S02 and the tests in S03.
- `ai-dev/active/I-00102/reports/I-00102_S05_CodeReviewFix_report.md` — step report listing the findings addressed and how.

## Requirements

### 1. Address every CRITICAL and HIGH finding

For each finding in S04 marked `CRITICAL` or `HIGH`:

1. Apply the recommended fix (or an equivalent one that satisfies the rationale).
2. Re-run the test that pins the related contract (or add one if it was missing). The reproduction test in `tests/integration/test_item_register_drift.py` must still pass after every fix.
3. Record in the report: finding id, file:line, what changed, which test verifies the fix is stable.

### 2. Address MEDIUM_FIXABLE findings unless they conflict with a higher-severity fix

MEDIUM_INFO and LOW findings are optional; document deferral with a one-line reason if you skip them.

### 3. Do NOT expand scope

You are fixing the review findings. You are NOT:
- Adding new acceptance criteria,
- Refactoring untouched files,
- Adding new tests for behaviours unrelated to the findings.

If a finding requires a change outside the manifest's `scope.allowed_paths`, raise a blocker — do not silently expand scope.

### 4. Keep tests green

After every fix, run the targeted suite:

```bash
uv run pytest tests/unit/test_item_commands_digest.py tests/integration/test_item_register_drift.py -v
```

(Skip `make test-unit` / `make test-integration` — S12/S13 own those.)

If a fix touches the migration file, also run `make migration-check`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make migration-check` if the migration file was touched.

## Test Verification (NON-NEGOTIABLE)

- `uv run pytest tests/unit/test_item_commands_digest.py tests/integration/test_item_register_drift.py -v` — targeted.
- Do NOT broaden to the full suite.

## Subagent Result Contract

```bash
mkdir -p ai-dev/work/I-00102/reports
uv run iw step-done I-00102 --step S05 \
  --report ai-dev/work/I-00102/reports/I-00102_S05_CodeReviewFix_report.md
```

```json
{
  "step": "S05",
  "agent": "code-review-fix-impl",
  "work_item": "I-00102",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "<list of files touched>"
  ],
  "findings_addressed": [
    {"id": "C1", "severity": "CRITICAL", "file": "orch/cli/item_commands.py:NNN", "fix": "<one-line>"},
    {"id": "H2", "severity": "HIGH", "file": "tests/integration/...", "fix": "<one-line>"}
  ],
  "findings_deferred": [
    {"id": "M3", "severity": "MEDIUM_FIXABLE|MEDIUM_INFO|LOW", "reason": "<one-line>"}
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok",
    "migration_check": "ok|skipped:not-touched"
  },
  "tests_passed": true,
  "test_summary": "tests/unit/test_item_commands_digest.py: N passed; tests/integration/test_item_register_drift.py: M passed",
  "tdd_red_evidence": "n/a — fix step",
  "blockers": [],
  "notes": ""
}
```

If FAILED: `uv run iw step-fail I-00102 --step S05 --reason "..."`.
