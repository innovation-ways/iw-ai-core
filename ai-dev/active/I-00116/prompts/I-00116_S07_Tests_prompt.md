# I-00116_S07_Tests_prompt

**Work Item**: I-00116
**Step**: S07
**Agent**: Tests

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers via pytest fixtures are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migration. Existing migration round-trips remain unchanged.

## Scope (`allowed_paths`)

You MAY only modify:

- `tests/unit/daemon/test_step_monitor_i00116_review_recovery.py` (new file)
- `tests/integration/test_fix_cycle_review_relaunch_cap.py` (new file)
- `tests/unit/test_review_prompt_scope.py` (new file)

NO production code. NO modifying existing tests (unless required to remove duplicated/obsolete coverage — justify each removal in your report).

## Input Files

- **Runtime state**: `uv run iw item-status I-00116 --json`
- **Design** (read §"Test to Reproduce" and "Acceptance Criteria" in detail): `ai-dev/active/I-00116/I-00116_Issue_Design.md`
- Production code being tested:
  - `orch/daemon/step_monitor.py` (S01)
  - `orch/daemon/fix_cycle.py` + `orch/daemon/batch_manager.py` (S03)
  - `agents/code-review-impl.md` + `commands/code-review-impl.md` + `skills/iw-workflow/SKILL.md` (S05)
- **Test conventions** (MANDATORY read): `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`
- **Existing tests for context**: `tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py` (the I-00113 sibling test — model your structure on this)

## Output Files

- Test files (above)
- Step report: `ai-dev/active/I-00116/reports/I-00116_S07_Tests_report.md`

## Context

This step writes the regression net for I-00116's three sub-fixes. Tests MUST be:

- **Semantic** — assert specific verdict values, specific DaemonEvent types, specific cap counts. Never shape-only (no `assert "foo" in data` without an exact-value check).
- **Order-independent** — pytest-randomly is on; fix any flaky-on-random-order test.
- **Mocked at the correct boundary** — see per-file requirements below.

## Requirements

### File (a) — `tests/unit/daemon/test_step_monitor_i00116_review_recovery.py`

Use the three tests verbatim from the design doc's `## Test to Reproduce` section:

1. `test_i00116_review_step_with_report_on_disk_is_recovered_not_crashed` (THE RED reproduction — fails pre-S01, passes after)
2. `test_i00116_review_step_without_report_still_marked_crashed`
3. `test_i00116_non_review_step_type_is_unchanged`

Add a fourth test:

4. `test_i00116_recovered_run_emits_daemon_event_with_verdict` — assert that on successful recovery, a `DaemonEvent` row with `type='step_run_recovered_from_report'` exists with `event_metadata['verdict']` matching the report's verdict. Use a real testcontainer-backed `db_session` so the DaemonEvent persists.

### File (b) — `tests/integration/test_fix_cycle_review_relaunch_cap.py`

Uses `db_session` + `test_project` fixtures from `tests/integration/conftest.py`. **MUST NOT mock the DB** (see CLAUDE.md "NEVER mock the database in integration tests"). Two tests:

1. `test_i00116_under_cap_review_relaunches_are_unaffected` — seed (cap-1) review StepRun rows for a single work item; trigger a relaunch decision; assert the item status remains unchanged and no `review_relaunch_cap_exceeded` event was emitted.
2. `test_i00116_at_cap_review_relaunch_transitions_item_failed_and_emits_event` — seed `cap` review StepRun rows; trigger a relaunch decision; assert:
   - `WorkItem.status == WorkItemStatus.failed`
   - exactly one `DaemonEvent` with `type='review_relaunch_cap_exceeded'`
   - `event.event_metadata['cap']` equals the cap value
   - `event.event_metadata['actual_count']` equals `cap`
   - `event.event_metadata['review_step_runs']` is a list of length >= 1
   - calling the cap-check a second time is idempotent (item stays `failed`, no second event emitted)

Set `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM` via `monkeypatch.setenv` for deterministic testing (use a small value like `3` to keep the tests fast). Remember the CLAUDE.md rule: **NEVER `importlib.reload(orch.config)` — use `monkeypatch.delenv()` / `monkeypatch.setenv()`**.

### File (c) — `tests/unit/test_review_prompt_scope.py`

Reads the master prompt files from disk and asserts text contents:

1. `test_review_prompt_references_allowed_paths` — assert both `agents/code-review-impl.md` and `commands/code-review-impl.md` contain `"allowed_paths"` somewhere in their text.
2. `test_review_prompt_does_not_recommend_unbounded_git_diff_head` — assert NEITHER file contains an instruction to use un-bounded `git diff HEAD` for diff scoping. (Allow the literal phrase to appear in negative context — e.g. "do not use git diff HEAD" is fine; the test should grep for instructional usage. Pragmatic test: assert the prompt does NOT contain the exact phrase `"diff against HEAD"` and DOES contain `"allowed_paths"` within 200 chars of the word "review" or "scope" — adjust to fit S05's actual wording.)
3. `test_iw_workflow_skill_documents_diff_scoping_convention` — assert `skills/iw-workflow/SKILL.md` contains a section/heading referencing `allowed_paths` AND `I-00116`.

### Test boundary discipline (CRITICAL)

- File (a) MUST mock at `_is_pid_alive` and `_probe_for_child` (the boundaries) — NOT at `_try_recover_completed_review_step` itself (that would mock past the bug class boundary).
- File (b) MUST use a real `db_session` (testcontainer-backed). No `MagicMock` for the DB — `FOR UPDATE` locking can't be tested with mocks.
- File (c) MUST read the actual prompt files on disk, not mock the filesystem.

### Targeted verification (no full-suite runs)

```bash
uv run pytest tests/unit/daemon/test_step_monitor_i00116_review_recovery.py \
              tests/integration/test_fix_cycle_review_relaunch_cap.py \
              tests/unit/test_review_prompt_scope.py -v
```

Do NOT run `make test-unit`, `make test-integration`, `make allure-integration`, or any full-suite gate. Full-suite execution is the downstream qv-gate's job — running it here blows the timeout budget (see I-00073/S03 post-mortem).

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Apply this rigorously: every assertion must be one that would fail if the production code regressed.

### Post-edit gate (MANDATORY)

After your final edit:

```bash
make format-check
make lint
```

Fix any violation YOUR test files introduced before exit.

## Constraints

- New files ONLY — do not touch production code.
- pytest-randomly compatibility: tests MUST pass under random order. If a test needs a fixture-scoped setup, declare the scope; don't rely on side effects from sibling tests.
- Use `db_session` from `tests/integration/conftest.py` (real DB) for file (b). Do NOT use the `MagicMock` `db_session` from `tests/unit/conftest.py` for it.
- If a test must use freeze_time or perf_counter mocking, follow the existing patterns in `tests/integration/test_keep_alive_poller_integration.py` and `tests/unit/test_keep_alive_service.py`.

## Step Done Contract

Report MUST contain:
```json
{"step": "S07", "agent": "Tests", "work_item": "I-00116",
 "files_changed": ["tests/unit/daemon/test_step_monitor_i00116_review_recovery.py",
                   "tests/integration/test_fix_cycle_review_relaunch_cap.py",
                   "tests/unit/test_review_prompt_scope.py"],
 "tests_added": <int>,
 "tests_passed": <int>,
 "test_summary": "...",
 "post_edit_gates": {"make format-check": "pass", "make lint": "pass"},
 "notes": "..."}
```

After writing the report, call `iw step-done S07 --report ai-dev/active/I-00116/reports/I-00116_S07_Tests_report.md`. **DO NOT exit without calling `iw step-done`.**
