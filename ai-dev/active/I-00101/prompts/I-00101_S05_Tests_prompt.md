# I-00101_S05_Tests_prompt

**Work Item**: I-00101 -- Scope-violation escalations strand work items with no UI surface or remedy
**Step**: S05
**Agent**: Tests

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures invoked by pytest are exempt; everything else is forbidden.

## ⛔ Migrations: agents generate, daemon applies

No migrations. The integration test uses the existing testcontainer DB fixture and `Base.metadata.create_all()` — no migration runs at agent time.

## Input Files

- `uv run iw item-status I-00101 --json`
- `ai-dev/active/I-00101/I-00101_Issue_Design.md` — design document (READ FIRST; the `Test to Reproduce` and `TDD Approach` sections name the test classes and the assertions you must include)
- `ai-dev/active/I-00101/reports/I-00101_S01_Backend_report.md` and `I-00101_S03_Frontend_report.md` — what was built
- `tests/conftest.py`, `tests/dashboard/conftest.py`, `tests/integration/conftest.py` — fixtures including `db_session`, `client`, etc.
- `tests/CLAUDE.md` — testing conventions
- `skills/iw-ai-core-testing/SKILL.md` — assertion-strength rules

## Output Files

- `ai-dev/active/I-00101/reports/I-00101_S05_Tests_report.md` — Step report
- Four new test files (paths in the design's File Manifest)

## Context

You write the reproduction + regression tests for I-00101. Four test files, each scoped to one slice of the fix.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "paths_added" in result` (shape only)
- GOOD: `assert ".gitleaks.toml" in result.paths_added` (semantic — verifies specific expected value)
- GOOD: `assert "scope_amended_by_operator" == evt.event_type` (semantic — specific name)
- GOOD: `assert evt.metadata["added_paths"] == [".gitleaks.toml"]` (semantic — exact list)

Every assertion must check a SPECIFIC value (or exact-shape match), not just "key is present" or "list is non-empty".

## Requirements

### Test file 1: `tests/unit/daemon/test_fix_cycle_budget_exemption.py`

Pure unit tests over the budget-counting predicate from S01. Use the testcontainer `db_session` fixture (the predicate uses PostgreSQL JSONB operators that won't work on SQLite).

Required tests (test name → assertion):

- `test_i00101_scope_escalated_cycle_not_counted_toward_per_step_budget` — Create a WorkflowStep + 1 FixCycle with `status=escalated, fix_metadata={"scope_violations": [".gitleaks.toml"]}`. Call the budget-evaluation path (whichever public/test-friendly seam S01 exposed; otherwise replicate the predicate-filtered count via SQL). Assert the row is NOT counted (count == 0).
- `test_i00101_scope_escalated_cycle_not_counted_toward_aggregate_budget` — Same setup but assert the aggregate-per-work-item count (over the same predicate-filter) also excludes the row.
- `test_i00101_non_scope_escalated_cycle_IS_counted` — Create a FixCycle with `status=escalated` but `fix_metadata={}` (or `fix_metadata={"some_other_key": "x"}`). Assert the row IS counted. This proves the filter is narrow (it does not exempt all escalations, only scope-driven ones).
- `test_i00101_failed_cycle_IS_counted` — Create a FixCycle with `status=failed`. Assert it IS counted (sanity check the predicate isn't accidentally exempting non-escalated rows).

### Test file 2: `tests/unit/daemon/test_scope_amendment.py`

Unit tests over the three helpers in `orch/daemon/scope_amendment.py`. Use `tmp_path` for filesystem fixtures (do NOT touch the real worktrees). For `latest_scope_violation`, use the testcontainer `db_session`.

Required tests:

- `test_i00101_amend_writes_both_manifests` — Build a fake worktree under `tmp_path/.worktrees/X` with a `ai-dev/active/X/workflow-manifest.json` containing minimal scope. Build a fake parent repo above it with the same manifest. Call `amend_allowed_paths(worktree, "X", [".gitleaks.toml"])`. Read both files and assert `".gitleaks.toml"` is in `scope.allowed_paths` of BOTH.
- `test_i00101_amend_is_idempotent_on_duplicate_paths` — Call `amend_allowed_paths` twice with the same paths. After the second call, the path appears in the list EXACTLY ONCE in both manifest files (use `Counter` or `list.count`).
- `test_i00101_amend_preserves_existing_keys_and_note` — Manifest starts with `_note`, `id`, `type`, `title`, `browser_verification`, `scope`, `steps`. After amend, all those keys still exist, in the same order, with the same values (`_note` text is byte-identical).
- `test_i00101_amend_handles_missing_parent_manifest_gracefully` — Build the fake worktree but no parent manifest. Call amend. Worktree manifest is updated; result's `manifests_updated` lists only the worktree path (no exception raised).
- `test_i00101_revert_runs_git_checkout_for_each_path` — Initialize a real `git` repo under `tmp_path/wt`. Commit a file. Edit the file. Call `revert_paths_in_worktree(wt, ["file.txt"])`. Assert the file content is restored to HEAD AND `RevertResult.reverted == ["file.txt"]` AND `failed == []`.
- `test_i00101_revert_records_failure_when_path_not_in_repo` — Call revert with a path that isn't tracked. Assert it appears in `failed`, not in `reverted`, and no exception is raised.
- `test_i00101_latest_scope_violation_returns_latest_cycle_violations` — Seed a step with two FixCycle rows: cycle 1 has `scope_violations=["a"]`, cycle 2 has `scope_violations=["b", "c"]`. Assert `latest_scope_violation(db, step.id) == ["b", "c"]` (the LATEST, by `cycle_number DESC`). If it returned `["a"]`, the test fails — proving "latest" semantics.
- `test_i00101_latest_scope_violation_returns_None_for_no_scope_cycle` — Step has no fix cycles. Assert returns `None`.
- `test_i00101_latest_scope_violation_returns_None_for_empty_scope_violations` — Step has one FixCycle with `status=escalated` but `fix_metadata={"scope_violations": []}` (empty list). Assert returns `None` (the dashboard uses truthiness — an empty list should NOT trigger badge rendering).

### Test file 3: `tests/dashboard/test_scope_blocked_badge.py`

Dashboard tests using the `client` fixture (only available under `tests/dashboard/`, per CLAUDE.md I-00067). Tests must:

- Seed a `WorkItem` with `status=in_progress` and a `WorkflowStep` in status `needs_fix`.
- Seed a `FixCycle` with `status=escalated, fix_metadata={"scope_violations": [".gitleaks.toml"]}`.
- GET the item detail page.
- Assert the response HTML contains the attribute-scoped substring `class="badge-scope-blocked"` (or whatever exact class S03 used; check the rendered output of `status_badge.html`). Use the attribute-scoped form, NOT bare `"badge-scope-blocked"` (per CLAUDE.md I-00067).
- Assert the rendered HTML for that step row does NOT contain `class="bg-warning text-warning-foreground"` (the generic `needs_fix` pill from `status_badge.html:14`) — proving the badge variant overrode the default.
- Assert the modal-trigger button exists with the correct `hx-get` URL attribute (`hx-get="/project/.../actions/item/.../scope/amend-modal/..."`). Use attribute-scoped assertion: `'hx-get="/project/<proj>/actions/item/<id>/scope/amend-modal/S<NN>"'`.
- Assert the existing **Restart** button is NOT rendered on that row (`<button>Restart</button>` should not appear for the scope-blocked row, or `hx-post` to `/restart-step/` should not).
- Assert the **Skip** button IS rendered on the same row.

Required test names:

- `test_i00101_scope_blocked_badge_renders_for_escalated_cycle_with_violations`
- `test_i00101_scope_blocked_badge_omitted_when_no_violations_on_needs_fix`
- `test_i00101_restart_button_hidden_on_scope_blocked_row`
- `test_i00101_amend_modal_trigger_url_is_correct`

### Test file 4: `tests/integration/test_scope_amend_endpoints.py`

End-to-end tests using the test `client` fixture against a real testcontainer DB. Tests must NOT mock the DB.

For each test, set up the full DB state (project, work_item, workflow_step in needs_fix, fix_cycle with scope_violations), then POST to the new endpoint and assert all side effects.

Use `tmp_path` for a fake worktree so the manifest writes don't touch real worktrees. Seed `WorkItem.worktree_path` to point at the fake worktree. Pre-populate the fake worktree with a `ai-dev/active/<ID>/workflow-manifest.json` containing a narrow `scope.allowed_paths`.

Required tests:

- `test_i00101_amend_writes_both_manifests_and_emits_event_and_restarts_step` — POST to amend endpoint with `paths=[".gitleaks.toml"]`. Assert: (a) worktree manifest's `scope.allowed_paths` now contains `".gitleaks.toml"`; (b) parent manifest's `scope.allowed_paths` now contains `".gitleaks.toml"` (if your fixture set up both — and the test asserts both were updated); (c) exactly one new `daemon_events` row with `event_type == "scope_amended_by_operator"` AND `entity_id == item.id` AND `metadata["added_paths"] == [".gitleaks.toml"]` AND `metadata["step_id"] == "S<NN>"`; (d) `workflow_step.status == StepStatus.pending`; (e) `workflow_step.started_at is None and step.completed_at is None`; (f) exactly one new `step_runs` row with `run_number == previous_run.run_number + 1` AND `status == RunStatus.pending`.
- `test_i00101_revert_runs_git_checkout_and_emits_event_and_restarts` — POST to revert endpoint. Initialize a real git repo in the fake worktree, commit a file containing `safe-content`, then mutate the file to `out-of-scope-edit`. After POST: (a) the file's content is back to `safe-content`; (b) the worktree manifest is UNCHANGED (revert does NOT amend); (c) one `scope_reverted_by_operator` event with `metadata["reverted_paths"]` containing the path; (d) same step-restart side effects as the amend test.
- `test_i00101_amend_endpoint_returns_422_on_non_scope_blocked_step` — Set up a `needs_fix` step WITHOUT any FixCycle (or with a non-scope escalation). POST to amend endpoint. Assert HTTP 422 AND the manifest file is UNCHANGED AND no daemon_event was emitted AND no new step_run was created.
- `test_i00101_amend_endpoint_rejects_paths_not_in_violation_set` — Step is scope-blocked with `scope_violations=[".gitleaks.toml"]`. POST with `paths=["something/else.py"]`. Assert HTTP 422 AND no manifest change AND no event AND no step_run.
- `test_i00101_amend_is_idempotent_at_the_endpoint_level` — POST twice with the same paths. Both calls return 200/302 (success). The path appears in `allowed_paths` exactly once. Two daemon_events ARE emitted (each operator action is auditable) AND two new step_runs are created (each request restarts).

## Project Conventions

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`. Key rules:

- NEVER mock the database in integration tests.
- NEVER connect to the live DB on port 5433 — use testcontainers.
- The `client` fixture is registered ONLY in `tests/dashboard/conftest.py`. Dashboard tests live in `tests/dashboard/`.
- Use `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in any test that touches `work_items` or `project_docs` (look at existing conftest.py setup for the pattern).
- Test names follow `test_<bug_id>_<scenario>` style.
- Assertion-strength rule: every assertion checks a SPECIFIC value or exact-shape match. Shape-only checks (`assert "key" in dict`, `assert len(x) > 0`) are a test-quality regression.
- CSS class assertions use the `class="…"` attribute-scoped form (per CLAUDE.md I-00067).

## TDD Requirement

This is the Tests step. The RED runs you must capture in `tdd_red_evidence`:

1. Run all four test files BEFORE the agent at S01/S03 ever ran their changes — IMPOSSIBLE here because the worktree already contains the fix. Instead, demonstrate RED at the per-test level by **reasoning** about each test against pre-S01 code (the design's `Test to Reproduce` and `TDD Approach` sections describe what each test would have shown against pre-fix code). Record the reasoning + the test ids in `tdd_red_evidence`.
2. **DO NOT** `git stash` or `git checkout HEAD~1 --` to manually create a RED state in the worktree (per the Implementation_Prompt_Template warning about thrash-prone manual reverts).
3. Then run all four new test files (GREEN run) and capture the pass count for `test_summary`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck` (zero errors on the new test files)
3. `make lint` (zero errors)

## Test Verification (NON-NEGOTIABLE)

Run ONLY the four new test files you wrote:

```bash
uv run pytest \
  tests/unit/daemon/test_fix_cycle_budget_exemption.py \
  tests/unit/daemon/test_scope_amendment.py \
  tests/dashboard/test_scope_blocked_badge.py \
  tests/integration/test_scope_amend_endpoints.py \
  -v --no-cov
```

Expected outcome: ALL pass.

Do NOT run `make test-unit` or `make test-integration` — those are S12/S13 QV gates.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "Tests",
  "work_item": "I-00101",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/daemon/test_fix_cycle_budget_exemption.py",
    "tests/unit/daemon/test_scope_amendment.py",
    "tests/dashboard/test_scope_blocked_badge.py",
    "tests/integration/test_scope_amend_endpoints.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "N passed, 0 failed (across 4 new files)",
  "tdd_red_evidence": "<per-test reasoning summary or full snippet — see TDD Requirement above>",
  "blockers": [],
  "notes": ""
}
```
