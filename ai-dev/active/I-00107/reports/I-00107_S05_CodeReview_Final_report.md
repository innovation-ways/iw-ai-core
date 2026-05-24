# I-00107 S05 Code Review — Final Report

**Step**: S05 (code-review-final-impl)
**Work Item**: I-00107 — `daemon reload` (SIGHUP) does not apply `.iw-orch.json` changes
**Date**: 2026-05-24

---

## Verdict: ✅ PASS

Zero CRITICAL, HIGH, or MEDIUM_FIXABLE findings.

---

## Pre-Flight Gate Results

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 889 files already formatted |
| `uv run pytest tests/unit/daemon/test_daemon_config_reload.py -v --no-cov` | ✅ 6 passed |
| `uv run pytest tests/unit/ -v --no-cov` | ✅ 3496 passed, 0 failed |

No new lint or format violations. No test regressions.

---

## What Was Reviewed

- Design doc: `I-00107_Issue_Design.md`
- Functional doc: `I-00107_Functional.md`
- Implementation: `orch/daemon/project_registry.py` + `orch/daemon/main.py`
- Tests: `tests/unit/daemon/test_daemon_config_reload.py`
- Step reports: S01, S02, S03, S04

---

## Cross-Cutting Checklist

### 1. End-to-end coverage of every AC ✅

| AC | Requirement | Verified by | Finding |
|----|-------------|-------------|---------|
| AC1 | `.iw-orch.json` drift rebuilds BatchManager | `test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes` — `post_manager is not pre_manager` + `"**/*.md" in post_allow` | None |
| AC2 | Next `_process_batch` reads new config | Transitive via AC1: new `BatchManager.project_config` is the source `_process_batch` reads (`batch_manager.py:460`). No caching layer between. | None |
| AC3 | `disabled`/`enabled` toggle refreshes BatchManager | `test_reload_rebuilds_manager_on_enabled_toggle` + `test_reload_removes_manager_on_disabled_toggle` | None |
| AC4 | `project_config_reloaded` DaemonEvent emitted | `test_reload_emits_project_config_reloaded_event` — exactly one event, `event_type="project_config_reloaded"`, `entity_id="demo"`, `"overlap_allow_patterns" in changed_fields` | None |
| AC5 | Regression test exists | Whole `test_daemon_config_reload.py` (6 tests) | None |

All five ACs have corresponding tests with semantic assertions. ✅

### 2. In-flight state safety on manager rebuild ✅

`BatchManager` (verified via `batch_manager.py:85-110`):
- No per-item progress stored in memory; all state lives in `batch_items` + `step_runs` + `daemon_events` in the DB.
- `_process_batch` re-queries the DB each tick (stateless per cycle).
- The rebuild path uses the **same** `_session_factory` the old manager used — same session lifecycle.
- `_process_batch` picks up from where the old manager left off; no item gets double-launched or skipped.

No in-flight state is dropped by the mid-run manager replacement. ✅

### 3. `disabled` branch removes manager cleanly ✅

`main.py:641-643` removes `self.managers[project_id]` via `self.managers.pop(project_id, None)`. The poll loop (`main.py:540-542`) guards on `manager is None` and skips the project. Behavioural symmetry confirmed. ✅

### 4. Backward compatibility / no migration ✅

- No `daemon_events` schema change (uses existing `emit_event` helper).
- No `projects.config` JSONB shape change (surfaces `config` field as-is from `.iw-orch.json`).
- No new Alembic revision in the diff (checked via `git diff HEAD~1`; confirmed no migration files touched). ✅

### 5. Functional doc faithfulness ✅

- Body: 478 words — ≤ 500 ✅
- No file paths, class names, code fences, SQL, or `orch/`/`dashboard/`/`scripts/` mentions ✅
- "What Changed" describes operator-visible behaviour (reload actually applies, new event for confirmation), not implementation mechanics ✅

### 6. TDD test names cross-check ✅

All five design-named tests present in the test file:

| Design test name | Test file location | Semantics |
|-----------------|-------------------|-----------|
| `test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes` | Line 87 | Object identity + new pattern present |
| `test_reload_unchanged_when_iw_orch_json_is_identical` | Line 132 | Object identity preserved (no churn) |
| `test_reload_rebuilds_manager_on_enabled_toggle` | Line 166 | Manager exists + reflects current `.iw-orch.json` |
| `test_reload_emits_project_config_reloaded_event` | Line 233 | Exactly one event, exact type, correct entity, field named in metadata |
| `test_reload_does_not_refresh_when_only_projects_toml_unchanged_iw_orch_json_unparseable` | Line 274 (`test_reload_rebuilds_manager_when_iw_orch_json_becomes_unparseable`) | Warning logged + manager rebuilt with fallback defaults |

All semantic — not just shape checks. ✅

### 7. Convention sweep ✅

- `DaemonEvent.metadata` Python attribute `event_metadata` — S01/S03 use `metadata=` keyword arg to `emit_event()`, the public API, not the internal attribute directly ✅
- Logger calls use `%r`/`%d`-style placeholders, not f-strings ✅
- No hardcoded ports, URLs, credentials ✅
- Imports organised correctly; no `from foo import *` ✅

---

## Findings

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00107",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "6 I-00107 tests passed; 3496 unit tests passed, 0 failed",
  "notes": "S01 (backend fix) and S03 (regression tests) are both clean. AC1-AC5 fully covered with semantic assertions. No migration, no schema change. BatchManager is stateless per-cycle — mid-run rebuild is safe. Poll loop handles disabled manager removal correctly. Functional doc is within 500-word budget with no implementation details. All project conventions followed. I-00107 is ready for S06 (QV gate)."
}
```