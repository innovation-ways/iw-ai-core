# CR-00017_S06_CodeReview_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step Being Reviewed**: S05 (backend-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md`
- `ai-dev/active/CR-00017/reports/CR-00017_S05_Backend_report.md`
- All files in S05's `files_changed`
- `orch/CLAUDE.md`, `docs/IW_AI_Core_Daemon_Design.md`

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S06_CodeReview_report.md`

## Review Checklist

### 1. Pipeline wiring correctness
- `run_pre_merge_dry_run` is called BEFORE `git squash-merge` in the merge flow.
- `run_post_merge_apply` is called AFTER `git squash-merge` — only if Phase 1 passed.
- `run_rollback` is called ONLY if Phase 2 failed.
- `is_merge_queue_frozen()` is checked at the TOP of every merge cycle; frozen → skip all batches until unfreeze.
- On `MIGRATION_INVALID`, the batch is NOT squash-merged; worktree is preserved for operator inspection.

### 2. Testcontainer hygiene
- Testcontainer is spawned via the `testcontainers` Python library (NOT raw docker calls, which would violate R1).
- Testcontainer is torn down after Phase 1 in a `finally`.
- Ryuk labels applied so containers self-destruct if the daemon crashes mid-phase.

### 3. State machine correctness
- `MIGRATION_INVALID` and `MIGRATION_ROLLED_BACK` exist as batch states (possibly via a chained alembic migration — reviewer verifies the migration file is present and autogenerate-clean).
- Transitions are additive — no existing batch state removed or repurposed.

### 4. `IW_CORE_AGENT_CONTEXT=true` in agent env
- Spotted in `batch_manager.py` where agents are spawned.
- Propagated through any shell wrapper (`sh -c`, `bash -c`, direct `subprocess.Popen`).
- Tested (or testable) — S11 will cover the formal test.

### 5. `daemon_events` usage
- Reuses existing writer — no new helper invented.
- `event_type` values are `"migration_pipeline"` and `"merge_queue_frozen"` exactly.
- `event_metadata` (NOT `metadata` — reserved) fields match the design.

### 6. Frozen queue behavior
- Writing a row with `event_metadata.active=true` is the freeze; `false` is the unfreeze.
- `is_merge_queue_frozen()` reads the latest row and defaults to `False` when the table is empty for this event_type.
- CLI unfreeze (S07) writes `active=false` with `acknowledged_by` set.

### 7. No agent-context guard violations
- `apply()` / `rollback()` in the daemon DO NOT inherit `IW_CORE_AGENT_CONTEXT=true` (the daemon process itself is not an agent). Verify env is clean in the daemon's own process; the flag is only set on children.

### 8. Error-path completeness
- Phase 1 failure → batch marked `MIGRATION_INVALID`, merge skipped, daemon moves to next batch.
- Phase 2 failure → rollback attempted; outcome matters.
- Phase 3 success → `MIGRATION_ROLLED_BACK`, queue continues.
- Phase 3 failure → frozen, loud alert, queue halts.

### 9. Smoke test documented in report
- S05 report describes the happy-path smoke the agent ran.
- No failing migration was ever applied to the live DB during development.

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW — standard. Fix in place. This step's review bar is high because it's the orchestration core.

## Subagent Result Contract

Standard code-review JSON.

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S06
uv run iw step-done CR-00017 --step S06 --report ai-dev/active/CR-00017/reports/CR-00017_S06_CodeReview_report.md
```
