# I-00107 S01 Backend Report — `daemon reload` config drift fix

**Step**: S01 (backend-impl)
**Work Item**: I-00107
**Completion**: `complete`
**Date**: 2026-05-24

---

## What Was Done

Fixed the daemon SIGHUP reload path so that **editing a project's `.iw-orch.json`** (without touching `projects.toml`) now correctly:

1. Detects the content drift in `ProjectRegistry.reload()` and reports it as a `"changed"` change-type.
2. Replaces `self.managers[pid]` with a freshly constructed `BatchManager` in `Daemon._reload_projects_if_stale()`.
3. Syncs the new config to the DB.
4. Emits a `project_config_reloaded` `DaemonEvent` for observability.

Additionally fixed two pre-existing bugs in the same method:
- **`disabled`** branch now removes `self.managers[project_id]` (so subsequent poll cycles skip it cleanly via the `manager is None` guard).
- **`enabled`** branch now rebuilds `self.managers[project_id]` with a fresh `BatchManager`.

---

## Files Changed

| File | Change Summary |
|------|----------------|
| `orch/daemon/project_registry.py` | Added `fields` import; updated docstring to list `"changed"` as a possible change value; added `elif old[pid] != new_projects[pid]` branch to detect `.iw-orch.json` content drift and emit `"changed"` |
| `orch/daemon/main.py` | Added `fields` import; fixed `disabled`/`enabled` branches to rebuild managers; added `elif change == "changed"` branch with manager rebuild, DB sync, and `DaemonEvent` emission |

---

## Diff Summary

### `project_registry.py` — 7 lines added
- Import: `from dataclasses import dataclass, field, fields` (added `fields`)
- Docstring: `"unchanged"` → `"unchanged", "changed"`
- `reload()`: one `elif` branch inserted between `"enabled"` check and the final `else`:
  ```python
  elif old[pid] != new_projects[pid]:
      # Both enabled (or both disabled) but .iw-orch.json content drifted.
      changes[pid] = "changed"
  ```

### `main.py` — ~42 lines added
- Import: `from dataclasses import fields`
- `disabled` branch: removed `if project_id in self.projects:` guard (always safe); added `self.managers.pop(project_id, None)`
- `enabled` branch: now constructs and stores `BatchManager` in `self.managers`
- `changed` branch (new): rebuilds manager, logs changed field names, syncs to DB, emits `project_config_reloaded` event

---

## Preflight Results

| Gate | Result | Notes |
|------|--------|-------|
| `make format` | ✅ ok | 1 file reformatted (ruff auto-fixed blank-line format on `changed_fields` def) |
| `make typecheck` | ✅ ok | Zero mypy errors |
| `make lint` | ✅ ok | All ruff checks passed |

---

## Test Results

```
217 passed, 0 failed (in tests/unit/daemon/)
```

No regressions introduced. The dedicated reproduction + regression tests for I-00107 (`tests/unit/daemon/test_daemon_config_reload.py`) are owned by S03 per the design doc's TDD Approach.

---

## TDD Note

`tdd_red_evidence`: `n/a — reproduction + regression tests delegated to S03 tests-impl per design doc TDD Approach`

---

## Blockers

None.

---

## Observations

- The `fields(old_cfg)` type narrowing required a guard (`if old_cfg is not None`) because `self.projects.get(project_id)` can return `None` — the typechecker needed it even though in practice `old_cfg` will always be non-None when `change == "changed"` (we're in the `"pid in old and pid in new_projects"` branch). This is correct defensive coding.
- The em-dash (`—`) in the original `message` string caused E501 line-length violations even though the string itself was <100 chars when split across lines — ruff counts the em-dash width as 1 but the actual line was 107 cols. Switched to a colon + split continuation to fix.
- The `enabled` branch fix aligns with AC3 of the design: toggling `enabled` in `projects.toml` from `false → true` now correctly creates a fresh `BatchManager` with the current `.iw-orch.json` baked in.