# F-00061 S05 Backend Integration — Step Report

## What Was Done

Integrated the QV baseline fingerprinting system into the daemon's control flow at two points:

### 1. Baseline compute hook in `batch_manager.py`

Added `_compute_qv_baselines()` method and inserted a hook call in `_launch_item()` after worktree setup succeeds and before `_launch_next_step()` is called.

The method:
- Short-circuits if `baseline_qv_enabled=False` (logs at DEBUG)
- Reads QV-gate steps from DB (`step_type == StepType.quality_validation`)
- Cross-references with `workflow-manifest.json` to get `gate` and `command` for each step
- Resolves base SHA via `git merge-base HEAD main`
- Runs each gate command, parses output via `GATE_PARSERS`, and upserts `QvBaseline` rows
- Per-gate fail-soft: WARNING log + continue on exception (AC6 fallback)
- Single commit at end

### 2. Subtraction integration in `fix_cycle.py`

Threaded `config: DaemonConfig` through `_get_review_findings` → `_get_qv_findings` (signature change at lines 245, 472, 476).

Modified `_get_qv_findings` to:
- Return legacy behavior if `baseline_qv_enabled=False`
- Return legacy behavior if step is not a recognized qv-gate (no manifest entry or gate not in `GATE_PARSERS`)
- On rebase detection (stored `base_sha != current_base_sha`): delete stale row, recompute fresh baseline via same logic as setup, persist, proceed
- Parse current gate output → `current_fp`
- `delta = subtract(current_fp, baseline_fp)`
- If `delta.failures == () and delta.unparseable == ()`: emit INFO log and return empty string (suppress fix-cycle trigger)
- Otherwise format findings from delta

Extracted helper functions:
- `_qv_findings_legacy()` — original `_get_qv_findings` logic for fallback
- `_get_gate_name_and_command()` — reads manifest for gate/command
- `_resolve_worktree_base_sha()` — git merge-base resolution
- `_recompute_baseline_for_gate()` — AC4 recompute logic
- `_format_qv_findings_from_delta()` — formats subtraction delta as findings string

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/batch_manager.py` | Added `_compute_qv_baselines()` hook after worktree setup; added QvBaseline, StepType imports |
| `orch/daemon/fix_cycle.py` | Added `config` threading; implemented baseline subtraction logic; added helper functions; added QvBaseline import |

## Verification

| Check | Result |
|-------|--------|
| `uv run mypy orch/daemon/batch_manager.py orch/daemon/fix_cycle.py` | ✅ Success: no issues found |
| `uv run ruff check orch/daemon/batch_manager.py orch/daemon/fix_cycle.py` | ✅ All checks passed |
| `uv run ruff format` | ✅ Files formatted |

## Hook Insertion Points

- `batch_manager.py`: hook call at line 318 (after `_emit_event` for "item_setup_completed", before `_launch_next_step`)
- `fix_cycle.py`: `_get_review_findings` call at line 245 (passes `config`); signature update at line 472; internal call at line 476

## Notes

- S01/S03 changes (`config.py`, `models.py`, `qv_baseline.py`, migration) were already present in worktree but not yet committed
- The kill switch (`baseline_qv_enabled=False`) disables both compute-at-setup and subtract-at-gate as required by AC5
- Legacy items (no baseline rows) fall through to `_qv_findings_legacy()` automatically (AC6)
- The `format` gate is intentionally excluded from `GATE_PARSERS` (not a regression — matches S03 design)