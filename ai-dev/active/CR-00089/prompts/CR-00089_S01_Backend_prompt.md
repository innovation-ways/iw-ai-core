# CR-00089_S01_Backend_prompt

**Work Item**: CR-00089 -- Fix-Cycle Pipeline Systemic Hardening (I-00113 RCA Follow-up)
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state. Allowed: testcontainers in pytest fixtures, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration. Do not run alembic commands.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00089 --json`
- `ai-dev/active/CR-00089/CR-00089_CR_Design.md` — design (read first; AC1, AC2, AC6 are this step's success bar)
- `orch/daemon/project_registry.py` — file to modify (`ProjectConfig` dataclass ~line 57, parsing block ~line 245)
- `projects.toml` — file to modify (add `[projects.iw-ai-core.always_in_scope]` table)

## Output Files

- `ai-dev/work/CR-00089/reports/CR-00089_S01_Backend_report.md`

## Context

You are implementing **Step 1 of 13** of CR-00089. The scope is narrow: add `always_in_scope_paths` to `ProjectConfig` and parse it from `projects.toml`. Do NOT touch `fix_cycle.py` — that is S02's job.

Read `CLAUDE.md` (root + `orch/CLAUDE.md`) before editing.

## Requirements

### 1. Add `always_in_scope_paths` field to `ProjectConfig` (orch/daemon/project_registry.py ~line 115)

Add a new field after `auto_amend_max_paths`:

```python
# Globally in-scope paths for all items in this project — fix cycles may
# touch these files without triggering scope violations regardless of the
# item's workflow-manifest allowed_paths. Supports the same glob patterns
# as allowed_paths. Empty list means feature disabled. Read from
# projects.toml: [projects.<id>.always_in_scope] paths = [...].
always_in_scope_paths: list[str] = field(default_factory=list)
```

### 2. Parse from projects.toml (orch/daemon/project_registry.py, _build_project_config function ~line 245)

Locate where `cascade_thrashing_threshold` and `auto_amend_allow_patterns` are parsed. Add parsing for `always_in_scope` immediately after, following the same defensive pattern (default to empty list, warn on invalid type):

```python
# always_in_scope — paths always in scope for fix cycles regardless of manifest
raw_always_in_scope = entry.get("always_in_scope", {})
if isinstance(raw_always_in_scope, dict):
    raw_paths = raw_always_in_scope.get("paths", [])
    if isinstance(raw_paths, list) and all(isinstance(p, str) for p in raw_paths):
        always_in_scope_paths = raw_paths
    else:
        logger.warning(
            "Project %r has invalid 'always_in_scope.paths' value %r — defaulting to []",
            project_id,
            raw_paths,
        )
        always_in_scope_paths = []
else:
    always_in_scope_paths = []
```

Then pass `always_in_scope_paths=always_in_scope_paths` in the `ProjectConfig(...)` constructor call at the bottom of `_build_project_config`.

### 3. Add entry to projects.toml for iw-ai-core

Locate the `[projects.iw-ai-core]` section in `projects.toml`. Add the new table immediately after the project's main table (before the next `[projects.*]` section):

```toml
[projects.iw-ai-core.always_in_scope]
paths = [
  "tests/assertion_free_baseline.txt",
]
```

### 4. TDD RED-first

Before adding the parsing code, write a unit test in `tests/unit/daemon/test_always_in_scope.py` that exercises `_build_project_config` (or the public `load_project_config` helper) with a mock `projects.toml` entry containing `always_in_scope.paths`. Confirm it FAILS (KeyError or AttributeError) against the current code. Record the RED output in the step report under "TDD RED evidence". Then make it GREEN by implementing the parsing.

### 5. Do NOT touch in this step

- `fix_cycle.py` (S02's job — consuming `always_in_scope_paths`)
- `step_monitor.py` (S03's job)
- Any test files other than `tests/unit/daemon/test_always_in_scope.py`

## Acceptance Criteria for this step

1. `ProjectConfig.always_in_scope_paths: list[str]` exists with default `[]`.
2. `projects.toml` for `iw-ai-core` has `[projects.iw-ai-core.always_in_scope]` with `paths = ["tests/assertion_free_baseline.txt"]`.
3. A project entry with no `always_in_scope` table produces `always_in_scope_paths = []` (AC6 from design).
4. `make lint && make typecheck` pass.
5. The new RED test passes GREEN after implementation.

## Hard Rules

- Allowed paths: `orch/daemon/project_registry.py`, `projects.toml`, `tests/unit/daemon/test_always_in_scope.py`, `ai-dev/work/CR-00089/reports/**`.
- Do NOT modify `fix_cycle.py`, `step_monitor.py`, or any other daemon file.

## Result Contract

Emit the standard `iw step-done` result contract JSON with:
- `tdd_red_evidence`: short string with the RED test name and failure mode.
- `files_changed`: exact list (relative paths).
- `tests_added`: new test names.
