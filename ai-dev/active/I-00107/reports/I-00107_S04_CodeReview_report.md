# I-00107 S04 Code Review Report — daemon reload regression tests

**Step**: S04 (code-review-impl)
**Work Item**: I-00107
**Date**: 2026-05-24
**Agent**: code-review-impl
**Step Reviewed**: S03 (tests-impl)

---

## What Was Reviewed

`tests/unit/daemon/test_daemon_config_reload.py` — the new test file S03 added. Also examined:
- `ai-dev/active/I-00107/I-00107_Issue_Design.md` (TDD Approach and Acceptance Criteria for the checklist)
- `ai-dev/active/I-00107/reports/I-00107_S03_Tests_report.md` (S03's self-report)

---

## Pre-Flight Results

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 889 files already formatted |
| `uv run pytest tests/unit/daemon/test_daemon_config_reload.py -v --no-cov` | ✅ 6 passed in 0.79s |

All five design-named tests are present. No new lint/format violations. All six tests pass green.

---

## Checklist Findings

### 1. All five named tests are present ✅

The design's TDD Approach lists five named tests. All five are present in the new file:

| Design test name | Found in test file | Line |
|---|---|---|
| `test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes` | ✅ `test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes` | 87 |
| `test_reload_unchanged_when_iw_orch_json_is_identical` | ✅ `test_reload_unchanged_when_iw_orch_json_is_identical` | 132 |
| `test_reload_rebuilds_manager_on_enabled_toggle` | ✅ `test_reload_rebuilds_manager_on_enabled_toggle` | 166 |
| `test_reload_emits_project_config_reloaded_event` | ✅ `test_reload_emits_project_config_reloaded_event` | 233 |
| `test_reload_does_not_refresh_when_only_projects_toml_unchanged_iw_orch_json_unparseable` | ✅ `test_reload_rebuilds_manager_when_iw_orch_json_becomes_unparseable` | 274 |

The fifth design test is named `test_reload_does_not_refresh_when_only_projects_toml_unchanged_iw_orch_json_unparseable`. S03 implemented it as `test_reload_rebuilds_manager_when_iw_orch_json_becomes_unparseable` — the behavior match is verified below (semantic correctness, item 2). No finding for the name difference.

Additionally, S03 added `test_reload_removes_manager_on_disabled_toggle` as a supplementary test for the AC3/AC4 corner case. This is within scope — the design doc's TDD Approach explicitly says "disable the project" as part of testing the toggle path.

### 2. Semantic correctness over shape ✅

Each of the five tests asserts specific expected values, not just shape or type:

- **Test 1 (AC1 reproduction)**:
  - `post_manager is not pre_manager` ✅ — proves object replacement (not just that manager exists)
  - `"**/*.md" in post_allow` AND `"**/*.md" not in pre_allow` ✅ — proves the specific new pattern is propagated and was absent before (not just that `overlap_allow_patterns` is a list)

- **Test 4 (AC4 event)**:
  - `mock_emit.assert_called_once()` ✅ — exactly one event (not just `emit_event.called`)
  - `call.kwargs["event_type"] == "project_config_reloaded"` ✅ — exact event type
  - `call.kwargs["entity_id"] == "demo"` ✅ — correct entity
  - `"overlap_allow_patterns" in changed_fields` ✅ — specific drifted field named in metadata

- **Test 2 (AC5 no-churn)**:
  - `post_manager is pre_manager` ✅ — same reference (not just that manager exists)

- **Test 3 (AC3 toggle)**:
  - `"**/*.md" in post_manager.project_config.overlap_allow_patterns` ✅ — manager reflects current `.iw-orch.json` (not just that manager exists)

- **Test 5 (unparseable fallback)**:
  - Warning logged ✅ — names the exact logged message pattern ("Invalid .iw-orch.json")
  - `overlap_allow_patterns != ["tests/**", "**/*.md"]` ✅ — manager rebuilt with new (fallback) config

### 3. Each test can fail if its target regresses ✅

- **Test 1** vs. removing the `"changed"` branch in `_reload_projects_if_stale`:
  - `post_manager is not pre_manager` would break → reference identity check fails ✅
  - `"**/*.md" in post_allow` would break → new pattern not present ✅

- **Test 3** vs. removing the `enabled` manager-rebuild in `_reload_projects_if_stale`:
  - `"**/*.md" in overlap_allow_patterns` would break → stale config used ✅

- **Test 4** vs. removing the `emit_event(project_config_reloaded, ...)` call:
  - `mock_emit.assert_called_once()` would break → no call made ✅

- **Test 2** vs. adding a "always rebuild on reload" regression:
  - `post_manager is pre_manager` would break → always rebuilt ✅

- **Test 5** vs. removing the `_build_project_config` warning path:
  - `any("Invalid .iw-orch.json" in msg for msg in warning_messages)` would break ✅

### 4. No live DB / testcontainer ✅

All six tests use `tmp_path` fixtures with no `db_session`, no testcontainer fixture, and no live DB connection. The design explicitly says this is a unit test and the daemon reload path operates in-memory. No finding.

### 5. Project conventions ✅

- File at `tests/unit/daemon/test_daemon_config_reload.py` ✅ (exact path)
- `importlib.reload(orch.config)` usage: **0 occurrences** ✅
- Raw `os.environ[...] = ...` usage: **0 occurrences** ✅
- No `make test-unit` / `make test-integration` invocation in test code ✅
- Test names follow `test_<descriptive_snake_case>` style ✅

### 5a. TDD RED Evidence ✅

S03 report states: `"n/a — tests-impl step adding regression coverage for already-merged S01 fix"`. This is accurate and consistent with the project convention for tests-impl steps where the production code is already merged. No finding.

### 6. Targeted-run discipline ✅

S03's Test Verification section shows `uv run pytest tests/unit/daemon/test_daemon_config_reload.py -v` — the targeted command, not `make test-unit`. Confirmed in S03's report. No finding.

---

## Verdict

```
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00107",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "6 passed, 0 failed",
  "notes": "All five design-named tests present with correct semantic assertions. No lint/format violations. No live DB usage. Project conventions respected. Targeted run discipline followed. S03 is ready for S05 (CodeReview_Final)."
}
```

**PASS**. No critical or high findings. S03 correctly implements all five named tests with semantic assertions and no convention violations. All six tests pass green. Proceed to S05.