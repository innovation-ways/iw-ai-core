# CR-00053_S07_CodeReview_Final_prompt

**Work Item**: CR-00053 -- Idempotent `iw next-id` via `--idempotency-key` flag
**Step**: S07
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- `ai-dev/active/CR-00053/CR-00053_CR_Design.md` -- Design
- All prior step reports under `ai-dev/work/CR-00053/reports/`
- The current state of every file in the CR's `scope.allowed_paths`

## Output Files

- `ai-dev/work/CR-00053/reports/CR-00053_S07_CodeReview_Final_report.md` -- Cross-agent review report

## Context

Cross-agent final review. The per-agent reviews (S05/S06) caught local issues; this step independently re-runs the gates and looks for integration issues that fall in the gaps between agents.

## Required Independent Checks

1. **Independent migration round-trip**: re-run `make migration-check`. Must be green. If it was green in S01 and red now, something landed between S01 and S07 that broke schema parity — flag CRITICAL.
2. **Independent unit + integration run** for the CR's own tests:
   ```bash
   uv run pytest tests/unit/test_id_allocations.py tests/integration/test_idempotency_key_cli.py -v
   ```
   Must be green. Note: this is **only** the new files — do NOT run the full suite (that's S13/S14).
3. **Model ↔ migration parity**: open the migration file and `orch/db/models.py` side by side. Verify the migration creates exactly what `Base.metadata.create_all()` would for `IdAllocation`. The most common drift: missing `postgresql_where=...` on the partial unique index. **CRITICAL** on parity break.
4. **Scope discipline**: `git diff main..HEAD --stat` (or the worktree equivalent). Verify the diff only touches paths in `scope.allowed_paths`. Files outside that list are scope creep. **CRITICAL** if found.
5. **Backwards-compatibility regression**: identify every caller of `allocate_next_id` in the repo, verify each still works without modification. Spot-check `orch/cli/batch_commands.py:326` specifically. **CRITICAL** if any positional caller is now broken.
6. **CLI output shape parity**: invoke `iw next-id --type cr` in a scratch testcontainer-backed test (or trust the integration tests if they cover this). Confirm output is bit-identical to today's no-key invocation. **HIGH** if drift.
7. **S05/S06 follow-through**: every CRITICAL/HIGH from S05 either has a corresponding fix in S06 or is documented as contested with rationale. **CRITICAL** if a CRITICAL finding was silently dropped.

## Output

Write the report at `ai-dev/work/CR-00053/reports/CR-00053_S07_CodeReview_Final_report.md`. Same severity scheme as S05. If everything passes, state explicitly "no CRITICAL/HIGH findings; S08 may be a no-op."

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00053",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/work/CR-00053/reports/CR-00053_S07_CodeReview_Final_report.md"
  ],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "independent reruns: migration-check OK; targeted unit+integration OK",
  "tdd_red_evidence": "n/a — final review step",
  "blockers": [],
  "notes": "Cross-agent findings: CRITICAL=X HIGH=Y MEDIUM=Z"
}
```
