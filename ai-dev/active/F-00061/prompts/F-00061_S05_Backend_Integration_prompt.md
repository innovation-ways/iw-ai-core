# F-00061_S05_Backend_Integration_prompt

**Work Item**: F-00061 -- Baseline QV gates to prevent fix-cycle scope expansion
**Step**: S05
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Same policy as S01. NEVER `docker compose up/down/restart`, `docker kill`, `docker rm`, `docker volume rm`. Read-only `docker ps/inspect/logs` is OK. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(You will NOT touch migrations in this step. S01 owns the migration; you read rows from the `qv_baselines` table, not schema. NEVER run `alembic upgrade|downgrade|stamp` against port 5433.)

## Input Files

- `ai-dev/active/F-00061/F-00061_Feature_Design.md` — **Acceptance Criteria AC1–AC6**, **Boundary Behavior** (all rows), **Invariants** (esp. 2, 5, 7)
- `ai-dev/active/F-00061/reports/F-00061_S01_Database_report.md` — for the QvBaseline model + migration revision id
- `ai-dev/active/F-00061/reports/F-00061_S03_Backend_QvBaseline_report.md` — for the public API of the pure module
- `orch/daemon/qv_baseline.py` (S03) — parsers, `subtract`, `fingerprint_to_jsonable` / `fingerprint_from_jsonable`, `GATE_PARSERS`
- `orch/db/models.py` — `QvBaseline` (S01), `WorkflowStep`, `StepRun`
- `orch/daemon/batch_manager.py` — particularly `_setup_worktree()` and `_launch_next_step()` around lines 316–335; you insert the baseline-compute hook between them
- `orch/daemon/fix_cycle.py` — particularly `_get_qv_findings()` at lines 559–594 and `_build_qv_fix_prompt_content()` at lines 680–718; you insert subtraction in `_get_qv_findings` so `_build_qv_fix_prompt_content` needs no changes
- `orch/config.py` — S03's `baseline_qv_enabled` flag; you consume it
- `orch/CLAUDE.md` + `orch/daemon/CLAUDE.md` — layer rules

## Output Files

- Modified: `orch/daemon/batch_manager.py` — hook baseline compute after worktree setup
- Modified: `orch/daemon/fix_cycle.py` — apply subtraction in `_get_qv_findings`
- `ai-dev/active/F-00061/reports/F-00061_S05_Backend_Integration_report.md`

**Explicitly out of scope for this step:**
- Any file in `tests/` (S07)
- Anything outside `orch/daemon/batch_manager.py` + `orch/daemon/fix_cycle.py`

## Context

S03 built the pure core; S01 built the storage. S05 is the glue: run the parsers at the right point in the daemon's control flow, persist the resulting rows, and consult them in the fix-cycle path. Two touch points — keep the diffs minimal and surgical. The scope gate (P1, commit `42feca2`) will enforce this at merge time.

## Requirements

### 1. Baseline compute hook in `batch_manager.py`

After `_setup_worktree()` returns successfully and BEFORE `_launch_next_step()` is called (lines ~316–318), insert a new private method call:

```python
self._compute_qv_baselines(batch_item, worktree_info)
```

Implement `_compute_qv_baselines` on the same class. Behaviour:

1. Short-circuit if `self.config.baseline_qv_enabled is False` — return immediately, log at DEBUG.
2. Read the item's workflow steps from DB filtered to qv-gate steps (`step_type == StepType.quality_validation`, and `gate` + `command` both non-null).
3. Resolve the worktree's current base SHA: `git merge-base HEAD main` run via the existing `subprocess` helper in this module, cwd set to the worktree path.
4. For each qv-gate step `s` with a `command`:
   - Run `s.command` in the worktree (same shell / env / timeout logic the gate uses when it runs for real — reuse any helper in this module; do NOT reinvent the gate runner). Capture combined stdout + stderr.
   - Resolve parser: `parser = GATE_PARSERS.get(s.gate)` from `orch.daemon.qv_baseline`. If None (unknown gate), skip with a WARNING log and no row.
   - `fp = parser(output)`; `payload = fingerprint_to_jsonable(fp)`.
   - Upsert a `QvBaseline(step_id=s.id, gate_name=s.gate, base_sha=<sha>, fingerprint=payload)` row. On unique-constraint conflict (pre-existing row for same triple — e.g. re-run after daemon restart), update `fingerprint` and `computed_at`.
5. On any exception from the subprocess or parser, log a WARNING and CONTINUE to the next gate. A single gate's baseline failing to compute must NOT block setup. The gate will fall back to legacy behavior (AC6) if its baseline is missing.
6. Commit the DB transaction once at the end of the method.

Rebase invalidation (AC4) is NOT done here — this is the initial compute. Invalidation happens in step 2.

### 2. Subtraction integration in `fix_cycle.py:_get_qv_findings`

Current signature ends with `findings` being handed to `_build_qv_fix_prompt_content`. Modify the method so:

1. Before composing the findings string at line ~584, determine if this is a qv-gate step with a recognised `gate` and a non-None `command`. If not, leave legacy behaviour untouched.
2. If `self.config.baseline_qv_enabled is False`, leave legacy behaviour untouched.
3. Resolve the worktree's current base SHA the same way as step 1. Call it `current_base_sha`.
4. Query `QvBaseline` for `(step_id=step.id, gate_name=step.gate)`:
   - Zero rows → no baseline → legacy behaviour (AC6).
   - One row with `base_sha != current_base_sha` → **rebase invalidation (AC4)**: delete the stale row, recompute fresh via the same logic as `_compute_qv_baselines` for this one gate, persist, then proceed with the freshly computed fingerprint as `baseline`.
   - One row with `base_sha == current_base_sha` → use it directly as `baseline`.
5. Parse the current gate's output with `GATE_PARSERS[step.gate]` → `current_fp`.
6. `delta = subtract(current_fp, baseline)`.
7. If `delta.failures == () and delta.unparseable == ()`: the gate is effectively a pass — emit an INFO log (`"[F-00061] Suppressed N pre-existing failures for %s/%s"`) and return an empty findings structure so the fix-cycle trigger upstream sees no new errors. (The actual gate pass/fail decision already happened in the qv-gate executor; S05 does not modify that. We only change what's FED to the fix-cycle.)
8. Otherwise compose findings from `delta` (formatted the same way `_build_qv_fix_prompt_content` currently consumes them — you may need a tiny adapter if the legacy path passed raw output; preserve the "Error Output" prose block but replace the content with the delta-formatted text).

DO NOT call `_build_qv_fix_prompt_content` or anything downstream of `_get_qv_findings`. Keep the subtraction entirely upstream.

### 3. Helper extraction (optional but encouraged)

If you find yourself duplicating the git-merge-base resolution, subprocess invocation, or parser lookup between `_compute_qv_baselines` and `_get_qv_findings`'s AC4 recompute branch, extract a private helper in one of the two modules (prefer `batch_manager.py` since setup owns the initial compute). The extraction MUST live within the two files you are already modifying — do NOT create a third file.

### 4. Kill switch semantics

`baseline_qv_enabled=False` disables BOTH compute-at-setup and subtract-at-gate. Toggling it off during a running pipeline leaves existing rows in place (they are harmless) but the gate path ignores them. AC5's test in S07 covers this.

### 5. Legacy items (AC6)

An item set up before F-00061 merged will have no `QvBaseline` rows. The subtraction path must observe "zero rows" and fall through to legacy behaviour without error. Never retroactively compute a baseline for a legacy item — the base SHA of an item already past setup could be anything.

### 6. Logging

All new log lines MUST use the module's existing logger and include the `[F-00061]` prefix so operators can `grep` the daemon log for baseline-related events. Levels:
- `INFO` — baseline computed / suppression count
- `WARNING` — baseline compute failed for a specific gate (with gate name + exception)
- `DEBUG` — kill switch path taken

## Project Conventions

- Follow `orch/daemon/` conventions (subprocess helpers, session lifecycle, error handling).
- DO NOT introduce new top-level modules.
- DO NOT modify `WorkflowStep` or any other model beyond reading it.
- DO NOT touch any test file — S07 owns tests.
- `dashboard/routers/items.py` must NOT be modified (step duration UI is unrelated — don't be tempted to "improve" it).

## TDD Requirement

S07 owns the tests. For your own verification, drive the change via a throwaway integration script that uses the test fixtures (`db_session`) but don't commit that script. Smoke-check each AC:
- AC3: call setup, count rows
- AC4: seed a row with old SHA, change HEAD, trigger gate path, observe row replaced
- AC5: set `baseline_qv_enabled=False`, re-run, observe zero rows

## Test Verification (NON-NEGOTIABLE)

Before reporting complete:
1. `uv run mypy orch/daemon/batch_manager.py orch/daemon/fix_cycle.py` — zero errors
2. `uv run ruff check orch/daemon/batch_manager.py orch/daemon/fix_cycle.py` — zero errors on changed lines (do NOT fix pre-existing errors; scope gate will block)
3. `uv run ruff format --check orch/daemon/batch_manager.py orch/daemon/fix_cycle.py` — clean
4. Diff against main — ONLY the two files above should appear. `git diff main..HEAD --name-only` must list exactly those two paths (plus any design-doc / report / prompt files under `ai-dev/active/F-00061/`).

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "backend-impl",
  "work_item": "F-00061",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py"
  ],
  "tests_passed": true,
  "test_summary": "mypy clean on modified files; ruff clean on changed lines; smoke checks of AC3/AC4/AC5 pass manually",
  "blockers": [],
  "notes": "hook insertion line numbers: batch_manager.py:<N>, fix_cycle.py:<M>"
}
```
