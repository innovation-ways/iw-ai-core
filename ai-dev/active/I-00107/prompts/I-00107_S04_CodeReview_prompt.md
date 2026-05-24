# I-00107_S04_CodeReview_prompt

**Work Item**: I-00107 -- daemon reload does not apply `.iw-orch.json` changes for an already-running project
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection only. Testcontainer fixtures in tests are exempt.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration expected. If you find one in the S03 diff, flag it as **CRITICAL**.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00107 --json`.
- `ai-dev/active/I-00107/I-00107_Issue_Design.md` — Design (TDD Approach + Acceptance Criteria are load-bearing)
- `ai-dev/active/I-00107/reports/I-00107_S03_Tests_report.md`
- `tests/unit/daemon/test_daemon_config_reload.py` — the new file under review

## Output Files

- `ai-dev/active/I-00107/reports/I-00107_S04_CodeReview_report.md`

## Context

You are reviewing the test coverage S03 added for **I-00107**.

Read the design's **TDD Approach** section first. It lists FIVE tests by name. Carry those five names into your review checklist — every one of them MUST be present in the new test file. A missing named test is a **CRITICAL** finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations in the new test file → **CRITICAL** with `"category": "conventions"`.

## Review Checklist

### 1. All five named tests are present

The design's TDD Approach names:

1. `test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes`
2. `test_reload_unchanged_when_iw_orch_json_is_identical`
3. `test_reload_rebuilds_manager_on_enabled_toggle`
4. `test_reload_emits_project_config_reloaded_event`
5. `test_reload_does_not_refresh_when_only_projects_toml_unchanged_iw_orch_json_unparseable`

Grep the new file for each. Any missing → CRITICAL.

### 2. Semantic correctness over shape (I003 lesson)

For each test, verify the assertions check **specific expected values**, not just shape:

- AC1 reproduction test: asserts `post_manager is not pre_manager` (object replacement) AND asserts the specific new pattern (`"**/*.md"`) is in `post.overlap_allow_patterns` AND not in `pre.overlap_allow_patterns`. **NOT** just `manager exists` or `allow_patterns is a list`.
- AC4 event test: asserts EXACTLY ONE event with `event_type="project_config_reloaded"` AND `metadata["changed_fields"]` includes the specific field name that changed. **NOT** just `emit_event.called` or `len(events) > 0`.
- Unchanged-config no-churn test: asserts `post_manager is pre_manager` (same reference) AND zero `project_config_reloaded` events. **NOT** just `manager exists`.

Any test that only verifies shape → **HIGH** with `"category": "testing"`.

### 3. Each test can fail if its target regresses

For each of the five tests, ask: "If I deleted the corresponding line in S01's fix, would this test fail?" If the answer is no for any test, flag as **HIGH** — the test is not load-bearing.

Specifically:
- Test 1 vs. removing the `"changed"` branch in `_reload_projects_if_stale` → must fail.
- Test 3 vs. removing the `enabled` manager-rebuild → must fail.
- Test 4 vs. removing the `emit_event(project_config_reloaded, ...)` call → must fail.

### 4. No live DB / testcontainer

The design says this is a **unit** test — no testcontainer, no `db_session` fixture, no live-DB connection. If S03 reached for a testcontainer fixture, that's a MEDIUM (testing) finding — the daemon reload path is in-memory and doesn't need DB round-trip; the integration suite already covers DB-side behaviour at a different layer.

### 5. Project conventions

- File lives at `tests/unit/daemon/test_daemon_config_reload.py` (exact path).
- No `importlib.reload(orch.config)` (per `tests/CLAUDE.md` Rule 2).
- No raw `os.environ[...] = ...`; use `monkeypatch.setenv` / `monkeypatch.delenv`.
- No `make test-unit` / `make test-integration` invocation inside the test code or the report (those are QV gates).
- Test names follow project style (`test_<descriptive_snake_case>`).

### 5a. TDD RED Evidence

`tests-impl` is exempt from the RED-first requirement. The report's `tdd_red_evidence` should be `"n/a — tests-impl step adding regression coverage for already-merged S01 fix"`. Anything else is a LOW finding (just record-keeping).

### 6. Targeted-run discipline

S03's `Test Verification` must show `uv run pytest tests/unit/daemon/test_daemon_config_reload.py -v` and NOT `make test-unit` or `make test-integration`. If the report shows the full-suite command, flag as MEDIUM (testing) — burns step budget per I-00073.

## Test Verification (NON-NEGOTIABLE)

Run the new test file yourself to confirm green:

```bash
uv run pytest tests/unit/daemon/test_daemon_config_reload.py -v
```

All five tests must pass. Report any failures as findings.

## Severity Levels

(See S02 prompt — same table.)

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00107",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed",
  "notes": ""
}
```
