# CR-00089_S02_Backend_prompt

**Work Item**: CR-00089 -- Fix-Cycle Pipeline Systemic Hardening (I-00113 RCA Follow-up)
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state. Allowed: testcontainers in pytest fixtures, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00089 --json`
- `ai-dev/active/CR-00089/CR-00089_CR_Design.md` — design (AC1–AC2 are this step's success bar)
- `ai-dev/work/CR-00089/reports/CR-00089_S01_Backend_report.md` — confirms `ProjectConfig.always_in_scope_paths` is now available
- `orch/daemon/fix_cycle.py` — file to modify (scope reconciliation functions `_load_allowed_paths`, `run_fix_cycle`, `_complete_fix_cycle`)

## Output Files

- `ai-dev/work/CR-00089/reports/CR-00089_S02_Backend_report.md`

## Context

You are implementing **Step 2 of 13** of CR-00089. S01 added `ProjectConfig.always_in_scope_paths`. This step threads that value into `fix_cycle.py`'s scope reconciliation so those paths are never flagged as violations.

Read the S01 report to confirm the field name before writing code. Read `CLAUDE.md` (root + `orch/CLAUDE.md`) before editing.

## Requirements

### 1. Understand the scope reconciliation flow in fix_cycle.py

There are two reconciliation sites to update:

**Site A** — `run_fix_cycle()` (~line 223, the entry-point that calls `run_llm_agent` and then reconciles):
```python
allowed = _load_allowed_paths(worktree_path, item_id)
# ... builds scope_block from allowed ...
# After agent runs:
violations = [p for p in agent_touched if not any(scope_match(p, pat) for pat in allowed + implicit)]
```

**Site B** — `_complete_fix_cycle()` (~line 1092, the post-cycle reconciliation):
```python
allowed = _load_allowed_paths(worktree_path, item_id)
# ...
violations = [...for p in ... if not any(scope_match(p, pat) for pat in allowed + implicit)]
```

Both sites load `allowed` from the manifest only. `project_config` is already threaded through to `_complete_fix_cycle` via its signature. Check whether `run_fix_cycle` also receives `project_config`.

### 2. Append always_in_scope_paths at both reconciliation sites

At each site, after loading `allowed`, extend it with the project config's global paths:

```python
allowed = _load_allowed_paths(worktree_path, item_id)
if project_config is not None:
    allowed = allowed + project_config.always_in_scope_paths
```

Do this BEFORE building `scope_block` in Site A (so agents also receive the expanded scope in their prompt) and BEFORE the violation filter in Site B.

### 3. Verify project_config is available at Site A

If `run_fix_cycle` (the top-level function) does not have `project_config` in its signature, add it as `project_config: ProjectConfig | None = None` and thread it through from the caller in `fix_cycle.py` (the daemon's `batch_manager.py` or wherever `run_fix_cycle` is invoked). Check call sites with `grep -n "run_fix_cycle(" orch/daemon/`.

### 4. Do NOT touch in this step

- `_load_allowed_paths()` internals — do not change what it reads, only augment the result at the call site.
- `scope_match()` — no changes needed.
- `project_registry.py` (S01's file).
- `step_monitor.py` (S03's file).
- Cascade reset logic (S04's file).

## Acceptance Criteria for this step

1. At both reconciliation sites in `fix_cycle.py`, `project_config.always_in_scope_paths` is appended to `allowed` when `project_config is not None`.
2. A fix cycle that modifies only `tests/assertion_free_baseline.txt` (in the always_in_scope list) produces zero violations.
3. `make lint && make typecheck` pass.

## Hard Rules

- Allowed paths: `orch/daemon/fix_cycle.py`, `ai-dev/work/CR-00089/reports/**`.
- Also allowed if `project_config` threading requires it: `orch/daemon/batch_manager.py` (call-site update only, no logic change).
- Do NOT modify the internals of `_load_allowed_paths`, `scope_match`, `_cascade_reset_upstream_qv_gates`, or `step_monitor.py`.

## Result Contract

Emit standard `iw step-done` JSON with:
- `files_changed`: exact list (relative paths).
- `call_sites_updated`: list of function/line-number pairs where always_in_scope_paths was threaded in.
