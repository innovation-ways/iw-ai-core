# CR-00089_S04_Backend_prompt

**Work Item**: CR-00089 -- Fix-Cycle Pipeline Systemic Hardening (I-00113 RCA Follow-up)
**Step**: S04
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state. Allowed: testcontainers in pytest fixtures, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00089 --json`
- `ai-dev/active/CR-00089/CR-00089_CR_Design.md` — design (AC4–AC5 are this step's success bar)
- `ai-dev/work/CR-00089/reports/CR-00089_S02_Backend_report.md` — confirms fix_cycle.py structure before adding a second change
- `orch/daemon/fix_cycle.py` — file to modify (`_cascade_reset_upstream_qv_gates`, `_peek_cascade_reset_ids`, `_complete_fix_cycle`)

## Output Files

- `ai-dev/work/CR-00089/reports/CR-00089_S04_Backend_report.md`

## Context

You are implementing **Step 4 of 13** of CR-00089. This step adds smarter cascade-reset logic to `fix_cycle.py`. `_cascade_reset_upstream_qv_gates` currently resets ALL upstream QV gates unconditionally. This change filters out gates whose file-type coverage is irrelevant to the files the fix cycle actually changed.

Read `CLAUDE.md` (root + `orch/CLAUDE.md`) before editing.

## Requirements

### 1. Add _GATE_RELEVANT_EXTENSIONS constant (fix_cycle.py, near top of file with other module-level constants)

```python
# CR-00089: maps gate names to file extensions whose changes should trigger
# a cascade reset of that gate. Gates not in this dict → _gate_is_relevant
# returns True directly (conservative: unknown gate always resets).
_GATE_RELEVANT_EXTENSIONS: dict[str, frozenset[str]] = {
    "lint": frozenset({".py", ".js", ".ts", ".css"}),
    "format": frozenset({".py"}),
    "typecheck": frozenset({".py"}),
    "unit-tests": frozenset({".py"}),
    "integration-tests": frozenset({".py"}),
    "diff-coverage": frozenset({".py"}),
    "assertion-check": frozenset({".py", ".txt"}),
    "migration-check": frozenset({".py"}),
    "security-sast": frozenset({".py"}),
}
_DEFAULT_GATE_EXTENSIONS: frozenset[str] = frozenset({".py"})  # fallback for external callers; _gate_is_relevant returns True directly for unknown gates
```

### 2. Add _gate_is_relevant helper (fix_cycle.py, near _GATE_RELEVANT_EXTENSIONS)

```python
def _gate_is_relevant(gate_name: str | None, changed_files: list[str]) -> bool:
    """Return True if any changed file has an extension relevant to this gate.

    Conservative: returns True when changed_files is empty (unknown change set)
    or when the gate name is not in _GATE_RELEVANT_EXTENSIONS (unknown gate).
    This ensures the cascade never silently skips a reset it should perform.
    """
    if not changed_files:
        return True  # unknown change set — reset conservatively
    if not gate_name or gate_name not in _GATE_RELEVANT_EXTENSIONS:
        return True  # unknown gate — reset conservatively
    relevant = _GATE_RELEVANT_EXTENSIONS[gate_name]
    return any(Path(f).suffix in relevant for f in changed_files)
```

(Import `Path` from `pathlib` if not already imported — check the existing imports first.)

### 3. Update _cascade_reset_upstream_qv_gates signature and filter (fix_cycle.py ~line 919)

Add `changed_files: list[str]` parameter (default `[]` for backward compat with any direct test callers):

```python
def _cascade_reset_upstream_qv_gates(
    db: Session,
    cycle: FixCycle,
    failing_step: WorkflowStep,
    project_id: str,
    changed_files: list[str] | None = None,
) -> list[str]:
```

Inside the function, after querying `upstream_gates`, filter before resetting:

```python
reset_ids: list[str] = []
for gate in upstream_gates:
    if not _gate_is_relevant(gate.gate, changed_files or []):
        continue  # skip gates irrelevant to the changed files
    gate.status = StepStatus.pending
    gate.started_at = None
    gate.completed_at = None
    reset_ids.append(gate.step_id)
return reset_ids
```

### 4. Update _peek_cascade_reset_ids to match (fix_cycle.py ~line 964)

`_peek_cascade_reset_ids` is the preview-only mirror used by the thrashing detector. Apply the same filter:

```python
def _peek_cascade_reset_ids(
    db: Session,
    failing_step: WorkflowStep,
    project_id: str,
    changed_files: list[str] | None = None,
) -> list[str]:
```

Apply the same `_gate_is_relevant` filter inside its for-loop (no DB writes — read-only mirror).

### 5. Update the callers in _complete_fix_cycle

Locate the two call sites in `_complete_fix_cycle` (~line 1192 and ~line 1197):

**Call 1** — `_peek_cascade_reset_ids` (thrashing preview):
```python
# Already computed changed_files above (~line 1273)
potential_reset_ids = _peek_cascade_reset_ids(db, step, project_id, changed_files=changed_files or [])
```

**Call 2** — `_cascade_reset_upstream_qv_gates` (actual reset):
```python
reset_step_ids = _cascade_reset_upstream_qv_gates(db, cycle, step, project_id, changed_files=changed_files or [])
```

Note: `changed_files` from `_files_changed_by_fix_cycle` is computed at ~line 1273 in `_complete_fix_cycle`. The peek call at ~line 1197 happens BEFORE this computation. You need to either (a) move the `_files_changed_by_fix_cycle` call earlier, or (b) call `_files_changed_by_fix_cycle` before the peek. Option (a) is simpler — move the call up to before the thrashing check block.

### 6. Do NOT touch in this step

- `project_registry.py` (S01's file).
- `step_monitor.py` (S03's file).
- The scope reconciliation sites modified in S02.
- Any gate's `command` field or QV gate execution logic.

## Acceptance Criteria for this step

1. `_GATE_RELEVANT_EXTENSIONS` and `_gate_is_relevant` exist in `fix_cycle.py`.
2. `_cascade_reset_upstream_qv_gates` accepts `changed_files` and filters by `_gate_is_relevant`.
3. `_peek_cascade_reset_ids` accepts and applies the same filter (AC4 from design).
4. When `changed_files=[]` or `None`, all upstream gates are reset (AC5 — conservative fallback).
5. `make lint && make typecheck` pass.

## Hard Rules

- Allowed paths: `orch/daemon/fix_cycle.py`, `ai-dev/work/CR-00089/reports/**`.
- Do NOT modify any function other than `_cascade_reset_upstream_qv_gates`, `_peek_cascade_reset_ids`, and `_complete_fix_cycle`'s two call sites.
- The default for `changed_files` must be `None` (not `[]`) on the signature to avoid the mutable-default-argument Python gotcha; use `changed_files or []` internally.

## Result Contract

Emit standard `iw step-done` JSON with:
- `files_changed`: exact list.
- `functions_modified`: list of function names changed.
- `conservative_fallback_confirmed`: boolean (True if empty changed_files still resets all gates).
