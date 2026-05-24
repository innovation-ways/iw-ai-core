# I-00107 S03 Tests Report — daemon reload regression tests

**Step**: S03 (tests-impl)
**Work Item**: I-00107
**Date**: 2026-05-24

---

## What Was Done

Created `tests/unit/daemon/test_daemon_config_reload.py` with 6 unit tests that pin the five acceptance criteria from the design doc. All tests target `Daemon._reload_projects_if_stale()` and `ProjectRegistry.reload()` using only tmp-path-backed files — no DB, no testcontainers.

---

## Files Changed

| File | Change Summary |
|------|----------------|
| `tests/unit/daemon/test_daemon_config_reload.py` | New test file — 6 tests, ~285 lines |

---

## Tests Implemented

### AC1 — `.iw-orch.json` drift rebuilds BatchManager (reproduction)
`test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes`

Mirrors the design doc's "Test to Reproduce" verbatim. Uses two assert checks:
- `post_manager is not pre_manager` — proves the manager object was **replaced** (pre-fix has the same reference)
- `assert "**/*.md" in post_allow` and `"**/*.md" not in pre_allow` — proves the new value is in the new config AND was absent in the old (semantic correctness, not just shape)

### AC5 — no-churn guard
`test_reload_unchanged_when_iw_orch_json_is_identical`

Writes `.iw-orch.json`, reloads (initial load), reloads again WITHOUT editing anything. Asserts `post_manager is pre_manager` — same object reference, no rebuild. Protects against "always rebuild on reload" regressions.

### AC3 — enabled/disabled toggle
`test_reload_rebuilds_manager_on_enabled_toggle` + `test_reload_removes_manager_on_disabled_toggle`

- **enabled toggle**: flips `enabled=false→true` in `projects.toml` AND writes a NEW `.iw-orch.json` at the same time. Asserts the manager is rebuilt with the **current** `.iw-orch.json` (`"**/*.md" in overlap_allow_patterns`). Correctly avoids asserting that the manager is absent before the toggle (pre-fix code creates managers for disabled projects too — only the disabled→enabled path was broken).
- **disabled toggle**: flips `enabled=true→false`. Asserts `"demo" not in daemon.managers`.

### AC4 — observability event
`test_reload_emits_project_config_reloaded_event`

Patches `emit_event` at module level. Edits `.iw-orch.json`, reloads. Asserts:
- Exactly one call (`mock_emit.assert_called_once()`)
- `event_type == "project_config_reloaded"`
- `entity_id == "demo"`
- `"overlap_allow_patterns" in metadata["changed_fields"]` (semantic — names the specific drifted field, not just "something changed")

### Fallback policy pin
`test_reload_rebuilds_manager_when_iw_orch_json_becomes_unparseable`

Writes a truncated JSON file. Asserts: warning logged AND manager rebuilt with new (default) config. Pins the existing `_build_project_config` policy — the fix propagates whatever config was parsed, with a warning when parse fails.

---

## Preflight Results

| Gate | Result | Notes |
|------|--------|-------|
| `make format` | ✅ ok | ruff auto-fixed import order + one formatting drift |
| `make typecheck` | ✅ ok | Zero mypy errors in 276 source files |
| `make lint` | ✅ ok | All ruff checks passed |

---

## Test Results

```
uv run pytest tests/unit/daemon/test_daemon_config_reload.py -v --no-cov
6 passed in 0.77s
```

All 6 tests pass.

---

## TDD Note

`tdd_red_evidence`: `"n/a — tests-impl step adding regression coverage for already-merged S01 fix"`

Per the design doc's TDD Approach, this is a `tests-impl` step (S01 production code already exists and was reviewed in S02). The reproduction test is structurally identical to the design doc's sketched test and would fail against pre-fix code (same reference, unchanged patterns) and pass against fixed code (new reference, new patterns). This was verified during design-time analysis documented in the design's Root Cause Analysis.

---

## Blockers

None.

---

## Notes

- The `_build_daemon` helper uses `MagicMock(spec=DaemonConfig)` for the `config` argument and patches `daemon._startup` to avoid triggering the DB-backed `_startup` chain (alembic guard, identity check, health check). This is consistent with the pattern used by `tests/unit/daemon/test_agent_subprocess_env.py`.
- `MagicMock(spec=Session)` is used for the session factory's yielded session — no real DB needed because `emit_event` is patched and `sync_project_to_db` is exercised via the actual code path (its SQL is executed against the MagicMock session, which is fine for testing the call was made).
- The `test_reload_rebuilds_manager_on_enabled_toggle` test deliberately changes both `projects.toml` (`enabled`) and `.iw-orch.json` content simultaneously — this is correct because AC3's requirement is that the newly-created manager uses the **current** `.iw-orch.json`, which is only verifiable if the content actually differs.