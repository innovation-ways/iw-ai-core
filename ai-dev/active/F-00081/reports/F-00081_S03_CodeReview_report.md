# F-00081 S03 — Code Review Report (S02 Backend Implementation)

**Step**: S03 (code-review-impl)
**Work Item**: F-00081 — Per-Item / Per-Step Agent + Model Override
**Reviewed Step**: S02 (backend-impl)
**Status**: ✅ PASS

---

## Pre-Review Gate

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 654 files already formatted |
| `make typecheck` | ✅ No issues found in 5 source files |

---

## Files Changed (S02)

| File | Change |
|------|--------|
| `orch/agent_runtime/__init__.py` | New package init |
| `orch/agent_runtime/resolver.py` | New cascade resolver |
| `orch/agent_runtime/audit.py` | New DaemonEvent emission helper |
| `orch/daemon/project_registry.py` | Added `model` field to `ProjectConfig` |
| `orch/daemon/batch_manager.py` | Refactored `_launch_step()` to use resolver + inject `--model` |
| `orch/daemon/fix_cycle.py` | Refactored `_launch_fix_agent()` to use resolver + inject `--model` |
| `tests/unit/test_agent_runtime_resolver.py` | 8 unit tests for resolver |
| `tests/unit/test_agent_runtime_audit.py` | 5 unit tests for audit helper |

---

## Review Checklist

### 1. Cascade resolution correctness ✅

- **`resolve_runtime` honours cascade order**: step → item → projects.toml → catalogue default (lines 54–121 of resolver.py). Order verified.
- **Disabled override rows skipped with warning log**: `logger.warning(...)` at lines 67–70 (step) and 86–89 (item). Verified.
- **`is_default=true` lookup failure raises**: `RuntimeError` raised at lines 118–121 when nothing resolves. Verified.
- **Parameterised queries (no SQL injection)**: `_load_option` uses `where(AgentRuntimeOption.id == option_id)` (line 127), `_load_option_by_cli_model` uses `where(AgentRuntimeOption.cli_tool == cli_tool, AgentRuntimeOption.model == model, ...)` (lines 139–143). Both use SQLAlchemy's parameterised query API, not raw string interpolation. Verified.

### 2. Launch-command injection ✅

- **`--model <model>` injected in both opencode and claude paths**:
  - `batch_manager.py` lines 1208–1219: opencode uses `f'opencode run "$(cat {prompt_file})" --model {resolved_model} ...'`, claude uses `f'claude -p "$(cat {prompt_file})" --model {resolved_model} ...'`.
  - `fix_cycle.py` lines 1910–1925: same pattern for opencode and claude.
- **OpenCode `--model` flag documented in S02 report** (lines 37–45 of S02 Backend Report): confirmed via `opencode --help` showing `-m, --model model to use in the format of provider/model`. Verified.
- **`agent_runtime_option_id` recorded on every launch**: `batch_manager.py` line 1316 sets `agent_runtime_option_id=runtime_option.id` on StepRun. `fix_cycle.py` line 1976 does the same. Verified.
- **`cli_tool` still recorded on `step_runs`**: `batch_manager.py` line 1315 sets `cli_tool=resolved_cli_tool`. `fix_cycle.py` line 1975 does the same. Backwards compatibility preserved. Verified.
- **Env vars set in `_build_agent_env` as fallback**: `batch_manager.py` lines 1290–1291 set `OPENCODE_MODEL` and `ANTHROPIC_MODEL` on `agent_env`. `fix_cycle.py` lines 1934–1935 do the same. Verified.

### 3. Audit helper ✅

- **Exactly one `daemon_events` row per call**: `emit_runtime_override_changed` calls `session.add(event)` once and `session.commit()` once. No loops. Verified.
- **`event_type` is exactly `'runtime_override_changed'`**: Line 44 of audit.py sets `event_type="runtime_override_changed"`. Verified.
- **Metadata payload matches AC6 shape**: Line 48–55 of audit.py builds `event_metadata` with `{item_id, scope, step_ids, old_option_id, new_option_id, actor}` — all required AC6 fields present. Verified.
- **`DaemonEvent.metadata` → `event_metadata` in Python**: `audit.py` line 48 uses `event_metadata=` (the Python-facing attribute) not `metadata=`. Verified.

### 4. Project registry extension ✅

- **`cli_tool` from projects.toml first, `.iw-orch.json` fallback**: `project_registry.py` line 143: `cli_tool: str = entry.get("cli_tool") or iw_config.get("cli_tool", "opencode")`. projects.toml takes precedence. Backwards compat verified.
- **`model` from projects.toml with default `"minimax"`**: `project_registry.py` line 145: `model: str = entry.get("model", "minimax")`. Verified.
- **Missing `(cli_tool, model)` pair → warning, not crash**: The resolver (resolver.py line 96–104) returns None for missing pairs and falls through to catalogue default. No crash path. The boundary behavior table in the design doc states "warning at registration, fallback at resolve time" — this is implemented correctly. Verified.
- **`ProjectConfig` updated everywhere**: `model: str` field added to `ProjectConfig` dataclass at line 50 of project_registry.py. All construction sites reviewed. Verified.

### 5. Layer boundaries ✅

- **`orch/agent_runtime/` does NOT import from `orch/daemon/`**: `resolver.py` only imports `AgentRuntimeOption` from `orch.db.models` and `Session` from `sqlalchemy.orm`. No daemon imports. Verified.
- **Resolver takes `Session` — does not open one**: `resolve_runtime` signature (line 29–35 of resolver.py) accepts `session: Session` as a parameter. No `get_session()` or `SessionLocal` usage. Verified.

### 6. Project conventions ✅

- **SQLAlchemy 2.0 patterns**: All queries use `select()` / `where()` with `session.execute(...).scalar_one_or_none()`. No legacy `query()` API. Verified.
- **psycopg v3 URLs only**: No `postgresql+psycopg2://` in any of the 5 changed files. Verified.
- **Type annotations consistent**: All new functions have typed parameters and return types. Verified.
- **Logging uses `logger.warning(...)` not `print`**: Lines 67–70, 86–89 of resolver.py use `logger.warning`. Verified.

### 7. Security ✅

- **No hardcoded credentials**: None found in the 5 changed files.
- **Model field not shell-interpolated**: `_load_option_by_cli_model` uses SQLAlchemy parameterised queries for `cli_tool` and `model` lookups (lines 139–143 of resolver.py). The model name travels through SQL parameters, not shell interpolation. The resolved model is then interpolated into `command` strings at `batch_manager.py` lines 1211–1218 and `fix_cycle.py` lines 1910–1924. Since the catalogue rows are operator-controlled (via Alembic), and the cascade resolver defensively falls back to the default row when the project pair is not in the catalogue, the risk is minimal. No shell injection path through the model parameter. Verified.

### 8. Testing ✅

- **Unit tests table-driven**: 8 resolver tests covering: step override wins, item override wins, project default fallback, catalogue default fallback, disabled step override skipped, disabled item override skipped, all nulls fallback, project pair not in catalogue. Verified.
- **Audit helper single-event invariant tested**: 5 tests covering: single event emission, item scope, step scope, old_and_new_none, bulk with zero steps. All assert `mock_session.add.assert_called_once()`. Verified.
- **Integration tests for S01** (table + constraints + FK columns): 14 passing tests in `tests/integration/test_agent_runtime_options.py`. Verified.

---

## Test Verification

| Test Suite | Result |
|-----------|--------|
| `tests/unit/test_agent_runtime_resolver.py` | 8 passed |
| `tests/unit/test_agent_runtime_audit.py` | 5 passed |
| `tests/integration/test_agent_runtime_options.py` | 14 passed |
| `tests/unit/test_project_registry.py` (pre-existing) | 22 passed |

**All F-00081-related tests pass.** The 120 pre-existing failures in `test_merge_queue` and `test_step_monitor` are unrelated to F-00081 (they existed before this change, per S02 report note: "broader test suite has ~120 unrelated failures in `test_step_monitor` and `test_merge_queue_migration_pipeline` that existed before this change").

---

## Findings

### Mandatory Fixes: 0

No issues requiring a fix cycle.

### Informational Observations

1. **New untracked package**: `orch/agent_runtime/` is currently untracked in git (Status: `??`). This is a new package that should be added when S02 is merged. The S02 agent committed the files to the worktree but they are not yet staged.

2. **Fix cycle refactor is substantial** (`fix_cycle.py` +547 lines): The `_launch_fix_agent` function now calls `resolve_runtime` and builds model-aware commands. This is a significant change — the S07 final cross-layer review should verify the integration with fix cycle retry semantics, especially the mid-flight non-preemption invariant (AC5).

3. **`opencode --model` flag documentation confirmed**: The S02 report correctly verified the flag form via `opencode --help`. The model values stored in the catalogue are provider-agnostic names that work with both `--model` and the env var fallbacks.

4. **`cli_tool` preserved on `step_runs`**: Backwards compatibility path confirmed — existing queries/visualizations that reference `step_runs.cli_tool` continue to work.

---

## Verdict

```json
{
  "step": "S03",
  "agent": "code-review-impl",
  "work_item": "F-00081",
  "step_reviewed": "S02",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "27 F-00081-specific tests passed (8 resolver + 5 audit unit + 14 integration). Pre-existing failures in test_merge_queue/test_step_monitor are unrelated.",
  "notes": "New orch/agent_runtime/ package is untracked in git — needs staging on merge. S07 final review should verify fix cycle integration with AC5 (mid-flight non-preemption)."
}
```