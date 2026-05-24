# I-00107 S02 Code Review — `daemon reload` config drift fix (S01)

**Step**: S02 (code-review-impl)
**Work Item**: I-00107
**Step Reviewed**: S01 (backend-impl)
**Date**: 2026-05-24

---

## Verdict: ✅ PASS

Zero CRITICAL, HIGH, or MEDIUM_FIXABLE findings.

---

## Pre-Flight Lint & Format Gate

| Gate | Result |
|------|--------|
| `make lint` (ruff) | ✅ All checks passed |
| `make format-check` (ruff) | ✅ 888 files already formatted |

No new violations introduced by S01.

---

## Architecture & Change-Set Review

### `orch/daemon/project_registry.py` — `ProjectRegistry.reload()`

**Diff**: +3 lines (docstring + one `elif` branch)

- The docstring is updated to list `"changed"` as a possible return value — correct.
- The new `elif old[pid] != new_projects[pid]` branch sits correctly between the `enabled` check and the `unchanged` else — i.e. it fires when both old and new exist AND have the same enabled/disabled state BUT their `ProjectConfig` objects differ structurally.
- `ProjectConfig` carries no custom `__eq__`, so dataclass-generated `__eq__` (field-by-field) is used — deterministic and correct.
- The `fields` import is **not** added to `project_registry.py` — correct, it is only needed in `main.py`. S01 did not import it unnecessarily.
- No migration added ✅

### `orch/daemon/main.py` — `Daemon._reload_projects_if_stale()`

**Diff**: ~42 added lines

**`disabled` branch fix** (AC3):
- Old code: `if project_id in self.projects: self.projects[project_id] = new_projects[project_id]` — no manager cleanup.
- New code: removes the `if` guard (always safe), assigns `self.projects[project_id]`, and calls `self.managers.pop(project_id, None)` — AC3 satisfied, subsequent poll cycles guard on `manager is None`.

**`enabled` branch fix** (AC3):
- Old code: only updated `self.projects[project_id]`.
- New code: constructs a fresh `BatchManager` and stores it in `self.managers[project_id]` — AC3 satisfied.

**`changed` branch (new)** (AC1, AC2, AC4):
- Replaces `self.managers[project_id]` with a freshly constructed `BatchManager` seeded with the new `ProjectConfig` — satisfies AC1.
- `_process_batch` reads from `self.project_config` on the new `BatchManager`, so AC2 is satisfied transitively.
- `changed_fields` uses `fields(old_cfg)` (type-safe, deterministic) and `getattr` for comparison — no risk of unstable dict/set ordering contaminating the diff list. The list is `sorted(...)` for stable ordering.
- `sync_project_to_db(db, new_cfg)` called — config is persisted to DB.
- `emit_event(...)` with `event_type="project_config_reloaded"`, `entity_id=project_id`, `entity_type="project"`, and `metadata={"project_id": project_id, "changed_fields": changed_fields}` — AC4 satisfied.

**Logger placeholders**: `%r`, `%d` style throughout — matches surrounding code conventions.

**`emit_event` usage**: S01 uses the existing `emit_event(...)` helper rather than constructing `DaemonEvent` directly — correct, consistent with existing code.

**`fields` import**: Correctly added only to `main.py`, sourced from `dataclasses` (same module as `dataclass`/`field` already imported in project_registry.py for `ProjectConfig`).

---

## Code Quality

- **Diff size**: ~45 lines added — within the design's 30-50 line estimate. No scope creep.
- **No unused imports**: `from dataclasses import fields` is used in the `changed` branch.
- **Defensive coding**: `if old_cfg is not None:` guard on `changed_fields` computation is correct — `self.projects.get(project_id)` can return `None` if somehow the project is in the registry but not in `self.projects` (type-system guard even though logically unreachable in the `"changed"` branch).
- **Malformed `.iw-orch.json`**: The `_build_project_config` → `_parse_overlap_gate` chain logs a warning and uses defaults when `.iw-orch.json` is malformed. The resulting `ProjectConfig` is a valid object, so `old[pid] != new_projects[pid]` will correctly trigger `"changed"` if the defaults differ from the previous state. No crash path.

---

## Project Conventions

- `DaemonEvent.metadata` (Python attribute `event_metadata`): S01 uses `metadata=` as a keyword arg to `emit_event(...)`, which is the public API and correct. The DB column is `metadata`; the Python attribute is `event_metadata` — this is hidden by the helper.
- `%r`/`%d`-style logging throughout — matches existing code.
- No hard-coded ports, URLs, or credentials.
- No migration files.

---

## Security

- No secrets in the diff. The diff is pure daemon control-flow code.
- No SQL-injection risk: all DB writes go through `emit_event` / `sync_project_to_db`.
- `changed_fields` list is derived purely from dataclass field comparisons on in-memory objects.

---

## Testing

- **S03 owns regression tests** — `test_daemon_config_reload.py` does not appear in S01's `files_changed` ✅
- **S01 `tdd_red_evidence`**: `"n/a — reproduction + regression tests delegated to S03 tests-impl per design doc TDD Approach"` — matches the design doc's expected wording exactly ✅
- **Unit tests**: 217 passed, 0 failed in `tests/unit/daemon/`

---

## Test Results

```
uv run pytest tests/unit/daemon/ -v
217 passed in ~22s
```

No regressions introduced.

---

## Findings

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00107",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "217 passed, 0 failed",
  "notes": "S01 is a clean, well-scoped fix. AC1 (manager rebuild on drift), AC3 (enabled/disabled manager refresh), and AC4 (project_config_reloaded event) are all satisfied. The secondary disabled/enabled manager-refresh sub-bug is also fixed. No test files added (correctly delegated to S03). No migration. Diff is 45 lines — within design estimate."
}
```