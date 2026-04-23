# F-00061_S06_CodeReview_Backend_Integration_prompt

**Work Item**: F-00061 -- Baseline QV gates to prevent fix-cycle scope expansion
**Step**: S06
**Agent**: code-review-impl
**Reviews**: S05 (Backend — daemon integration)

---

## ⛔ Docker is off-limits

(Same policy as S01. Read-only `docker ps/inspect/logs` only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(S05 should not have touched migrations. If it did, flag CRITICAL out-of-scope.)

## Input Files

- `ai-dev/active/F-00061/F-00061_Feature_Design.md` — **Acceptance Criteria AC1–AC6**, **Boundary Behavior** rows 1, 6, 7, 8, 9, **Invariants** 2, 5, 7
- `ai-dev/active/F-00061/reports/F-00061_S05_Backend_Integration_report.md` — S05's self-report + line numbers of hook insertion
- `orch/daemon/batch_manager.py` — S05's hook
- `orch/daemon/fix_cycle.py` — S05's subtraction integration
- `orch/daemon/qv_baseline.py` (S03) — for public API surface you can confirm S05 used correctly
- `orch/db/models.py` — `QvBaseline` (S01) to confirm S05 queries/upserts consistently
- `orch/config.py` — `baseline_qv_enabled` flag
- `orch/CLAUDE.md` + `orch/daemon/CLAUDE.md` — layer rules and daemon patterns

## Output Files

- `ai-dev/active/F-00061/reports/F-00061_S06_CodeReview_Backend_Integration_report.md`

## Context

S05 is the most integration-sensitive step in this feature — it touches the daemon's control flow at two points (setup + fix-cycle trigger). A subtle bug here — wrong insertion order, missing commit, silent exception-swallow that hides a broken baseline — can make AC1/AC2 fail silently in production. Your job is to treat this module like a compiler: every statement justified, every branch covered, every error path traced to a logged observable event.

## Review Checklist

### CRITICAL — must pass

1. **Hook placement in `batch_manager.py`**: `_compute_qv_baselines` is called AFTER `_setup_worktree()` returns successfully and BEFORE `_launch_next_step()` (around lines 316–318 per the reconnaissance). Not before setup (worktree doesn't exist), not after first step (races against the gate's own run).
2. **Kill switch short-circuits BOTH paths**:
   - `_compute_qv_baselines` returns at the top if `config.baseline_qv_enabled is False`
   - The subtraction path in `_get_qv_findings` falls through to legacy behaviour if the flag is False
3. **Subtraction replaces, not augments, the legacy finding path**: trace `_get_qv_findings` line by line. When the delta is empty, the method returns an empty findings structure — it does NOT return the full current-run findings alongside an unused delta. When the delta is non-empty, the "Errors to Fix" content comes from the delta, NOT the raw current-run output.
4. **Rebase invalidation works end-to-end (AC4)**: when the DB has a row with `base_sha != current_base_sha`, S05's code (a) deletes the stale row, (b) recomputes against `current_base_sha`, (c) persists a fresh row, (d) uses the fresh fingerprint for subtraction in the same call. No TOCTOU window that would let a stale row resurface.
5. **Legacy items fall through gracefully (AC6)**: zero baseline rows → legacy behaviour → no exception. Confirm by reading the query path and checking there's no implicit assumption that a row must exist.
6. **DB commit hygiene**: `_compute_qv_baselines` commits exactly once at the end; the AC4 recompute in `_get_qv_findings` commits after delete+insert (so a crash between delete and insert doesn't leave the item with ZERO baselines — that's worse than stale). Confirm with a close read of the transaction boundaries.
7. **No changes outside `orch/daemon/batch_manager.py` and `orch/daemon/fix_cycle.py`** — `git diff main..HEAD --name-only` lists exactly those two production paths plus the F-00061 design/report artefacts. Any third file → CRITICAL out-of-scope.
8. **Scope discipline**: `dashboard/routers/items.py` is NOT touched. Other QV fix-cycle hooks are NOT rewritten. No collateral refactors.

### HIGH — should pass

9. **Failure isolation per gate**: a single gate's baseline compute throwing an exception does NOT abort the loop — the next gate still gets a chance. Verified by reading the `try/except` boundary inside the `for gate in ...:` loop.
10. **Rebase case handles concurrent baseline compute**: if two processes race on AC4 (delete+insert), the unique constraint on `(step_id, gate_name, base_sha)` means the second writer's insert fails cleanly and the reader re-selects. Spot-check the `IntegrityError` path.
11. **Logger prefix `[F-00061]`** on every new log statement so operators can grep.
12. **`_compute_qv_baselines` log levels**: INFO on success per gate, WARNING on per-gate exception. Never silent.
13. **Unparseable handling**: `delta.unparseable` from S03's subtraction is forwarded into the findings structure (never dropped silently). This upholds the fail-safe from Boundary Behavior row 3.
14. **Subprocess safety**: the gate's command is invoked with the same safety posture as the existing qv-gate executor (shell=False or careful shell=True usage, proper timeout, explicit cwd, no injection risk from untrusted gate strings).
15. **`fingerprint_to_jsonable` / `fingerprint_from_jsonable` round-trip is respected**: what S05 writes and reads back has the same shape as what S03's serializers produce. No ad-hoc JSON shaping in S05.

### MEDIUM_FIXABLE — fix if noticed

16. Docstrings on new private methods explain their role and reference F-00061.
17. Type hints on new private methods.

### MEDIUM_SUGGESTION

18. Consider logging the baseline row count after setup (INFO) so operators see "[F-00061] Computed baselines for N gates" as a single summary line.

## Verification Commands (read-only)

- `uv run mypy orch/daemon/batch_manager.py orch/daemon/fix_cycle.py` — zero errors
- `uv run ruff check orch/daemon/batch_manager.py orch/daemon/fix_cycle.py` — zero errors on S05's changed lines
- `uv run ruff format --check orch/daemon/batch_manager.py orch/daemon/fix_cycle.py` — clean
- `git diff main..HEAD --name-only` — exactly the declared scope

Ad-hoc behavior verification (OPTIONAL — S07 owns real tests):

```python
# Pseudo-REPL sanity trace
# 1. With baseline_qv_enabled=False: _get_qv_findings returns legacy shape
# 2. With enabled + matching baseline: delta is correct, log emits suppression count
# 3. With enabled + stale SHA: row at old SHA is deleted, row at new SHA exists after call
```

## Report

Standard CodeReview report. Findings grouped by severity. Overall verdict **pass** only if zero CRITICAL + zero HIGH.

Call `iw step-done` or `iw step-fail` with `--report`.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00061",
  "steps_reviewed": ["S05"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "mypy clean; ruff clean; scope gate would pass (only declared files changed)",
  "notes": ""
}
```
