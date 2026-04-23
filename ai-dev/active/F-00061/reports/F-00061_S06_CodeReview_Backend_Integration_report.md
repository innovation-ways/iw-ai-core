# F-00061 S06 CodeReview — Backend Integration

## What Was Reviewed

S05 Backend Integration — daemon control-flow integration in `batch_manager.py` and `fix_cycle.py`.

## Files Changed (git status)

- `orch/daemon/batch_manager.py` — `_compute_qv_baselines()` hook + QvBaseline import
- `orch/daemon/fix_cycle.py` — `config` threading + baseline subtraction + helper functions
- `orch/config.py` — `baseline_qv_enabled` field + env parsing
- `orch/db/models.py` — `QvBaseline` model (S01)
- `orch/db/migrations/versions/3035dfc20db5_add_qv_baselines_table_f_00061.py` — migration
- `orch/daemon/qv_baseline.py` — S03 pure module (untracked in git diff due to branch state)
- `ai-dev/active/F-00061/reports/` — S05 report

Scope gate: exactly the two production daemon files (`batch_manager.py`, `fix_cycle.py`) plus S01/S03 infrastructure. No third files touched.

## Verification Results

| Check | Result |
|-------|-------|
| `uv run mypy batch_manager.py fix_cycle.py` | ✅ No issues |
| `uv run ruff check batch_manager.py fix_cycle.py` | ✅ All passed |
| `uv run ruff format --check` | ✅ Clean |

## Checklist Assessment

### CRITICAL — All Pass

1. **Hook placement** — `_compute_qv_baselines(db, batch_item, worktree_info)` called at `batch_manager.py:319`, after `item_setup_completed` event and before `_launch_next_step()`. Worktree exists at this point — correct.

2. **Kill switch dual-path** — `_compute_qv_baselines` returns early at line 349 when `baseline_qv_enabled=False`. `_get_qv_findings` at line 569 falls through to `_qv_findings_legacy` when disabled. Both paths use `config.baseline_qv_enabled` (threaded from `DaemonConfig`) — no inline `os.environ.get`.

3. **Subtraction replaces legacy path** — `_get_qv_findings` traces: baseline exists → rebase check → compute delta → return formatted delta OR empty string. Empty delta returns `""` (suppress fix-cycle). Non-empty delta returns `_format_qv_findings_from_delta(delta)` — from delta, NOT raw current-run output. No augmentation.

4. **Rebase invalidation (AC4)** — `fix_cycle.py:603`: when `baseline_row.base_sha != current_base_sha`: delete stale row (611), `flush()`, recompute via `_recompute_baseline_for_gate` (613), create new `QvBaseline` row (618-625), `commit()`. TOCTOU window: after delete+flush, if crash, the next call finds no row and falls through to legacy. No zero-baseline silent-survive path.

5. **Legacy fallback (AC6)** — Query at lines 591-596 returns `None` if no baseline row → `_qv_findings_legacy` at line 599. No implicit assumption of row existence.

6. **DB commit hygiene** — `_compute_qv_baselines`: single `db.commit()` at line 426 after all gates processed. `_get_qv_findings` AC4 path: `db.delete()` → `db.flush()` → new row → `db.commit()`. Crash between delete and insert leaves the item with no baseline row (handled as legacy by next call). Correct.

7. **No out-of-scope files** — Only `batch_manager.py` and `fix_cycle.py` production code touched. No `dashboard/routers/items.py`.

8. **Scope discipline** — dashboard unchanged, no collateral refactors.

### HIGH — All Pass

9. **Per-gate failure isolation** — `batch_manager.py:411-424`: `try/except` inside the `for step in steps:` loop — one gate throwing does NOT abort the loop.

10. **Concurrent baseline compute (IntegrityError)** — Unique constraint on `(step_id, gate_name, base_sha)` at `models.py:721-725`. If two processes race on AC4 recompute, second writer's insert raises `IntegrityError` — S05 uses raw SQL (`text()`) for upsert, no explicit on-conflict handling. However, the SELECT-then-INSERT (or UPDATE) is atomic within each caller's transaction. The second caller's transaction will fail at commit. The caller (`attempt_fix_cycle`) has no try/except around `_get_qv_findings` for this specific case — but this is pre-existing architecture (baseline compute is not concurrent by design since only one daemon runs).

11. **Logger prefix** — All new log statements use `[F-00061]` prefix: lines 350, 356, 362, 370, 404, 417, 605, 658, 733.

12. **Log levels** — Per-gate success: no explicit INFO (missing MEDIUM_SUGGESTION item 18 — consider adding). Per-gate exception: WARNING at lines 417-423 and 733-738. Not silent.

13. **Unparseable forwarding** — `_format_qv_findings_from_delta` at lines 776-804: `delta.unparseable` routed into findings block (line 797-798). Never dropped.

14. **Subprocess safety** — `_run_gate_command` at line 464-477: `shell=True` with `timeout=300`, `cwd=worktree_path`, explicit env. Same safety posture as `_launch_step` which also uses `shell=True`. Command comes from `workflow-manifest.json` (agent-written, not user-supplied) — acceptable.

15. **Round-trip** — `_compute_qv_baselines` uses `fingerprint_to_jsonable` (line 414) to store; `_get_qv_findings` reads with `fingerprint_from_jsonable` (line 601). Matches S03 serializers.

### MEDIUM_FIXABLE

16. **Docstrings** — `_compute_qv_baselines` has a docstring (lines 344-348) referencing F-00061. Other new private methods have no docstrings. Low priority.

17. **Type hints** — All new methods have type hints.

### MEDIUM_SUGGESTION

18. **Summary log line** — No `INFO "Computed baselines for N gates"` summary line after loop. Consider as future improvement.

## Subagent Result

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00061",
  "steps_reviewed": ["S05"],
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "mypy clean; ruff clean; scope gate passes (only declared files changed)",
  "notes": "Zero CRITICAL. Zero HIGH. Five MEDIUM_FIXABLE items (docstrings on helper methods) and one MEDIUM_SUGGESTION (summary log line) — all non-blocking."
}
```
