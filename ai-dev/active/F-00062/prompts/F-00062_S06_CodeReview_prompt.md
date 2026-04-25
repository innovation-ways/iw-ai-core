# F-00062_S06_CodeReview_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step Being Reviewed**: S05 (backend-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

State-changing docker commands MUST live only in `orch/daemon/worktree_compose.py`. This step's S05 code may invoke `docker ps` (read-only) and call into `worktree_compose.down()`. Verify that no NEW state-changing docker calls were added outside the S03 module. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No alembic execution against live orch DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design doc, S01-S05 reports
- `orch/daemon/worktree_reaper.py` (new) and/or section in `worktree_compose.py`
- `orch/daemon/batch_manager.py` (modified)
- `orch/daemon/main.py` (modified)
- `tests/unit/daemon/test_worktree_compose.py` (extended)
- `tests/unit/daemon/test_batch_manager_worktree_hooks.py` (new)

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S06_CodeReview_report.md`

## Context

You are reviewing the daemon-side lifecycle wiring: when `up()` and `down()` get called, the reaper's classification logic, and the daemon-restart re-attach path. The biggest risks here are missed teardown calls (zombie containers) and reaper false-positives (active worktrees being torn down).

## Review Checklist

### 1. Lifecycle hook completeness
- The terminal `BatchItemStatus` set is `{merged, failed, stalled, skipped, migration_invalid, migration_rolled_back, migration_rebase_failed, setup_failed}`. **`archived` and `restarted_discarded` are NOT in `BatchItemStatus`** — they are batch-level statuses (`BatchStatus`); flag any code that treats them as item terminals as a HIGH finding.
- Verify a single source of truth exists for terminal-status detection (e.g., `TERMINAL_BATCH_ITEM_STATUSES` constant or `is_terminal_batch_item_status()` helper); flag duplicate hard-coded lists as MEDIUM_FIXABLE.
- Every code path that transitions `BatchItem.status` to ANY value in the terminal set calls `worktree_compose.down(batch_item.id, batch_item.worktree_compose_path)` BEFORE or AFTER the transition (consistent with existing patterns).
- Use `git grep -n "BatchItemStatus\.\(merged\|failed\|stalled\|skipped\|migration_invalid\|migration_rolled_back\|migration_rebase_failed\|setup_failed\)"` to find every transition site. Cross-check `merge_queue.py`, `batch_manager.py`, `migration_pipeline.py`, `step_monitor.py`, `fix_cycle.py` at minimum.
- For any transition site without a `down()` call, that's a HIGH finding (zombie risk).
- The setup path: `up()` is called AFTER `worktree_setup.sh` succeeds, BEFORE the first step launches. On `up()` failure, status flips to `setup_failed` (the new enum value added by S01) and step launch is skipped.

### 2. Reaper classification correctness
- A container labelled `iwcore.batch_item=<id>` where `<id>` matches a BatchItem with `status NOT IN (terminal)` is classified `active` and NOT reaped (Invariant #7 — CRITICAL if violated)
- A container with no matching BatchItem is `orphan` and reaped
- A container with matching BatchItem in a terminal state is `stale` and reaped
- Malformed labels (e.g., empty `iwcore.batch_item=`) are reaped as orphan (defensive)

### 3. Race conditions
- The "reap only if container >10s old" mitigation (see design doc Notes → Risks) is implemented OR the lifecycle hooks ensure the BatchItem row is committed BEFORE `up()` invokes `docker compose up`. Verify one of these is true.
- Reaper runs sequentially with the lifecycle hooks (single-threaded daemon — no real concurrency, but verify there's no surprise threading)

### 4. Daemon-restart re-attach
- Re-attach scans only non-terminal items with non-NULL `worktree_compose_path` (Invariant #6)
- Re-attach does NOT call `up()` again for items where `is_alive()` returns True (AC5)
- Items where `is_alive()` returns False but the BatchItem is non-terminal: code logs and lets the next poll cycle re-setup. Verify there's no infinite loop or bad state.

### 5. Idempotency
- `down()` calls handle the "already torn down" case
- `up()` is not called twice for the same item (the lifecycle path guards this via status check)
- Reaper is safe to run repeatedly

### 6. DaemonEvent emission
- Every reap emits an event with classification + labels
- Every lifecycle action emits an event (phase='up' or phase='down' or phase='reap')
- `DaemonEvent.event_metadata` is the correct Python attribute (NOT `metadata` — see `orch/CLAUDE.md` gotcha)

### 7. Tests
- All eight reaper tests + four batch_manager hook tests from S05 exist and pass
- Tests use realistic fixtures (mock the docker subprocess; use real Session objects against a testcontainer for the BatchItem lookups in classify())

### 8. Project conventions
- Sync only, no asyncio/threading
- Reuse existing daemon scheduling for the periodic reaper (don't introduce a new mechanism)
- Append-only DaemonEvent

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make lint` and `make quality`
3. Trace at least three terminal-state transitions through the codebase by hand and confirm each calls `down()`

## Severity Levels

| Severity | Examples |
|----------|----------|
| CRITICAL | Reaper reaps active worktree (Invariant #7); missed `down()` call leaves persistent zombies; `up()` called twice |
| HIGH | One terminal transition path missing `down()`; re-attach calls `up()` for already-running stack; race condition in setup |
| MEDIUM_FIXABLE | Missing test; weak DaemonEvent metadata; new threading mechanism added unnecessarily |
| MEDIUM_SUGGESTION | Reaper-as-section vs separate module judgment |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00062",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
