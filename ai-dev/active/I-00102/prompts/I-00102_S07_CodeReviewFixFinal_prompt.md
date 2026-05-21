# I-00102_S07_CodeReviewFixFinal_prompt

**Work Item**: I-00102 — iw register silently ignores design-package drift; approve must auto-refresh workflow_steps
**Fixing Findings From**: S06 (code-review-final-impl)
**Step**: S07
**Agent**: code-review-fix-final-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

If you must edit the migration file (e.g. column placement / naming), edit the existing revision in place — never stack a second migration. Re-run `make migration-check` to confirm.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00102 --json`.
- `ai-dev/active/I-00102/reports/I-00102_S06_CodeReviewFinal_report.md` — final review findings.
- `ai-dev/active/I-00102/I-00102_Issue_Design.md` — acceptance contract.
- All files touched by S01–S05.

## Output Files

- Edits to the production files and tests identified by S06's findings.
- `ai-dev/active/I-00102/reports/I-00102_S07_CodeReviewFixFinal_report.md`

## Requirements

### 1. Address every CRITICAL and HIGH finding from S06

For each finding:
1. Apply the recommended fix (or an equivalent that satisfies the rationale).
2. If the finding asks for a missing test, add it inside `tests/integration/test_item_register_drift.py` or `tests/unit/test_item_commands_digest.py` (keep the file locality from S03).
3. Re-run the targeted suite after every fix. Reproduction test must continue passing.
4. Record in the report: finding id, file:line, what changed, which test verifies the fix.

### 2. AC traceability table is correct in the final report

After your fixes, every AC in the design must trace to a real code-path + test. Update the final-review report's `ac_coverage` table accordingly (or, if S06's table was already correct, confirm it.)

### 3. Address MEDIUM_FIXABLE findings unless they conflict with a higher fix

Defer MEDIUM_INFO / LOW with a one-line reason in the report.

### 4. Do NOT expand scope

Same rules as S05: stay within `scope.allowed_paths`; do not refactor untouched files; raise a blocker if a finding requires out-of-scope edits.

### 5. Re-run full pre-flight + targeted tests after the LAST fix

The next steps are QV gates (S08–S13) — anything you miss here costs a fix-cycle there.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make migration-check` if the migration file was touched.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_item_commands_digest.py tests/integration/test_item_register_drift.py -v
```

Do NOT broaden to `make test-unit` / `make test-integration`.

## Subagent Result Contract

```bash
mkdir -p ai-dev/work/I-00102/reports
uv run iw step-done I-00102 --step S07 \
  --report ai-dev/work/I-00102/reports/I-00102_S07_CodeReviewFixFinal_report.md
```

```json
{
  "step": "S07",
  "agent": "code-review-fix-final-impl",
  "work_item": "I-00102",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "<list>"
  ],
  "findings_addressed": [
    {"id": "C1", "severity": "CRITICAL", "file": "...", "fix": "..."}
  ],
  "findings_deferred": [
    {"id": "L1", "severity": "LOW", "reason": "..."}
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok",
    "migration_check": "ok|skipped:not-touched"
  },
  "tests_passed": true,
  "test_summary": "tests/unit/...: N passed; tests/integration/...: M passed",
  "tdd_red_evidence": "n/a — fix step",
  "blockers": [],
  "notes": ""
}
```

If FAILED: `uv run iw step-fail I-00102 --step S07 --reason "..."`.
