# I-00117_S02_CodeReview_Backend_prompt

**Work Item**: I-00117 -- Daemon silently dead-ends a non-fixable, non-retryable failed step
**Step**: S02 — Per-agent review of S01
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Standard policy (testcontainers + read-only introspection only). Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00117 --json`
- `ai-dev/active/I-00117/I-00117_Issue_Design.md`
- `ai-dev/active/I-00117/reports/I-00117_S01_Backend_report.md`

## Output Files

- `ai-dev/active/I-00117/reports/I-00117_S02_CodeReview_Backend_report.md`

## Diff scoping (I-00116)

Restrict your review diff to `scope.allowed_paths` in
`ai-dev/active/I-00117/workflow-manifest.json`. Files outside it are either later
steps' work or scope violations.

## Review Bars (CRITICAL → must pass)

1. **The silent branch is gone.** The `else` branch in `batch_manager.py` no
   longer just logs + returns; it now escalates. Confirm there is no remaining
   code path where a failed, non-fixable, non-retryable step returns without
   emitting a `DaemonEvent` AND changing status.
2. **Escalation event emitted.** `handle_recovery_exhausted_escalation` emits a
   `DaemonEvent(event_type="step_recovery_exhausted")` with `event_metadata`
   carrying `step_id` and `failure_reason`. Uses `event_metadata` (not
   `metadata`).
3. **Status transitions.** `batch_item.status` → `failed` and the parent
   `work_item.status` → `failed`, committed. The item can no longer remain
   `in_progress` / the batch `executing` after this path runs.
4. **SPEC_MISMATCH preserved.** The `SPEC_MISMATCH:` reason still routes to
   `handle_spec_mismatch_escalation`, NOT the new path. The two are mutually
   exclusive.
5. **No `FixCycle` created** by the new path; no double-commit; no refactor of the
   surrounding routing ladder beyond the `else` branch.
6. **Scope**: only `orch/daemon/fix_cycle.py` + `orch/daemon/batch_manager.py`
   touched (plus `ai-dev/**`).

Classify findings CRITICAL / HIGH / MEDIUM / LOW. If any CRITICAL/HIGH:
`iw step-fail S02 --item I-00117 --reason "Review FAIL: <summary>"`. Otherwise
write the report and `iw step-done` (orchestrator handles the CLI calls in
daemon mode — follow the manifest contract).
