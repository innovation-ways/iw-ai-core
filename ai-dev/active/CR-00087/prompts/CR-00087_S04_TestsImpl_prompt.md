# CR-00087_S04_TestsImpl_prompt

**Work Item**: CR-00087 -- Auto-amend scope violations matching per-project allow-patterns
**Step**: S04
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Allowed exceptions: testcontainers via existing pytest fixtures (they self-label and self-destruct via Ryuk), read-only `docker ps`/`inspect`/`logs`, `./ai-core.sh`/`make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration. Do not run alembic upgrade/downgrade against the live DB.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00087 --json`.
- `ai-dev/active/CR-00087/CR-00087_CR_Design.md` — Design document (read AC2, AC3, AC4 carefully).
- `ai-dev/work/CR-00087/reports/CR-00087_S01_BackendImpl_report.md` — registry parsing report.
- `ai-dev/work/CR-00087/reports/CR-00087_S02_BackendImpl_report.md` — `should_auto_amend` helper report.
- `ai-dev/work/CR-00087/reports/CR-00087_S03_BackendImpl_report.md` — `_complete_fix_cycle` integration report.
- `tests/integration/test_scope_amend_endpoints.py` — file to extend.
- `tests/conftest.py` — existing testcontainer fixtures.
- `tests/CLAUDE.md` — testing conventions and rules.
- `skills/iw-ai-core-testing/SKILL.md` — IW AI Core testing standards.

## Output Files

- `ai-dev/work/CR-00087/reports/CR-00087_S04_TestsImpl_report.md` — Step report

## Context

You are implementing **Step 4** of CR-00087. This step adds integration tests that exercise the full auto-amend path end-to-end — from a real workflow-manifest.json on disk, through a real `_complete_fix_cycle` call against a testcontainer Postgres, asserting both the manifest mutation and all DB side effects.

Why integration rather than unit: `_complete_fix_cycle` writes to the manifest file, mutates multiple DB rows in one transaction, emits DaemonEvents, and creates a new StepRun. Unit tests with extensive mocking would test the mocks more than the behaviour. The existing `tests/integration/test_scope_amend_endpoints.py` already tests the manual operator flow against a testcontainer — extend that file to test the daemon auto-amend pass with the same fixture style.

## Requirements

### 1. Read `tests/integration/test_scope_amend_endpoints.py` carefully

Understand the existing test fixture pattern (worktree tmp_path setup, manifest writing, FixCycle seeding, DB session usage). The new tests should match that pattern — do NOT introduce a new fixture style.

Also read `tests/CLAUDE.md` for the testcontainer rules (port replacement, FTS function/trigger application after `create_all`, no live-DB connections, etc.) and `skills/iw-ai-core-testing/SKILL.md` for assertion-strength expectations.

### 2. Positive integration test: `test_complete_fix_cycle_auto_amends_when_all_violations_match`

The flow:

1. Set up a tmp worktree path with `ai-dev/active/CR-00087/workflow-manifest.json` containing `scope.allowed_paths = ["orch/daemon/scope_amendment.py"]` (just the file the fake agent will "legitimately" touch).
2. Set up the parent worktree manifest at the appropriate location (write the `.git` pointer file so `_resolve_parent_manifest` finds the parent; or use the test fixture's existing helper for this).
3. Seed a `WorkItem`, `WorkflowStep`, and a `StepRun` for the step.
4. Build a `ProjectConfig` with `auto_amend_allow_patterns=["tests/**", "**/*.md"]` and `auto_amend_max_paths=10`.
5. Seed a `FixCycle` in `status=running` with `fix_metadata = {"worktree_path": "<tmp_path>", "pre_cycle_paths": [<existing files>]}`.
6. Simulate the agent touching out-of-scope files by writing two new files into the worktree: `tests/unit/new_test.py` and `docs/new_notes.md` (both fall under the allow-patterns).
7. Call `_complete_fix_cycle(db, cycle, project_id, now, project_config=cfg)`.
8. Assertions:
   - The `FixCycle` row has `status = escalated` and `fix_metadata.scope_violations` contains both new paths (the escalation step ran).
   - A `scope_violation_escalation` DaemonEvent was emitted with the violations payload.
   - The worktree's workflow-manifest.json now has both new paths appended to `scope.allowed_paths`.
   - The parent manifest also has both new paths appended (if `_resolve_parent_manifest` finds the parent in your fixture setup).
   - A new `StepRun` exists with `run_number = previous + 1`, `status = pending`.
   - The `WorkflowStep` row has `status = pending`, `started_at = None`, `completed_at = None`.
   - A `scope_auto_amended` DaemonEvent was emitted with `added_paths`, `manifests_updated`, `matched_patterns` keys present in `event_metadata`.

### 3. Negative integration test: `test_complete_fix_cycle_does_not_auto_amend_when_violation_falls_outside_allow_patterns`

Same setup as the positive test, BUT:

- The fake agent touches `orch/daemon/fix_cycle.py` (definitely NOT in `auto_allow_patterns=["tests/**", "**/*.md"]`) in addition to a tests file.
- Call `_complete_fix_cycle`.
- Assertions:
  - The `FixCycle` is `escalated` with violations populated.
  - `scope_violation_escalation` event emitted.
  - The worktree manifest's `scope.allowed_paths` is UNCHANGED (no amend ran).
  - The `WorkflowStep` has `status = needs_fix` (today's manual flow takes over).
  - NO `scope_auto_amended` event exists.
  - NO new `StepRun` was created.

### 4. Negative integration test: `test_complete_fix_cycle_does_not_auto_amend_when_count_exceeds_max_paths`

Setup:

- `project_config.auto_amend_allow_patterns=["tests/**"]`, `auto_amend_max_paths=2`.
- The fake agent creates 3 new files all under `tests/`.
- Call `_complete_fix_cycle`.
- Assertions (same as test 3): escalated + needs_fix + no amend + no `scope_auto_amended` event + no new StepRun.

### 5. Negative integration test: `test_complete_fix_cycle_does_not_auto_amend_when_feature_disabled`

Setup:

- `project_config.auto_amend_allow_patterns=[]` (feature off — default for projects without the config block).
- The fake agent touches `tests/foo.py` (would match if the feature were on).
- Call `_complete_fix_cycle`.
- Assertions (same as test 3).

This test guards backwards compatibility — the most important assertion in the suite.

### 6. Fixture / helper notes

- The testcontainer Postgres is supplied by `tests/conftest.py` fixtures (`db_session` or similar). Do NOT spin up a new container.
- Replace `postgresql+psycopg2://` with `postgresql+psycopg://` in any URL you handle (per CLAUDE.md).
- Apply `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` — the existing conftest does this for you; do not duplicate.
- DO NOT mock `amend_allowed_paths` or `_emit_event` — exercise the real code path. Mocking the database in these tests would defeat the integration test's purpose (see CLAUDE.md critical rule: "NEVER mock the database in integration tests").
- DO NOT mock `_captured_paths` — instead, write the files to the tmp worktree before calling `_complete_fix_cycle` so the real `_captured_paths` sees them.

### 7. RED capture

Pick the positive test (`test_complete_fix_cycle_auto_amends_when_all_violations_match`). Implement it FIRST (before any S03 code if you're running in fresh-worktree mode; if S03 is already merged, this test should still fail because the test itself is new — capture the assertion that fails). Run via:

```bash
uv run pytest tests/integration/test_scope_amend_endpoints.py::test_complete_fix_cycle_auto_amends_when_all_violations_match -v
```

Confirm the failure mode is one of:
- `AssertionError` on the `scope_auto_amended` event check (S03 not yet wiring the event), OR
- `AssertionError` on the manifest update (S03 not yet calling `amend_allowed_paths`), OR
- Test passes (means S03 is already in place — capture the green run output instead and note "n/a — green from start; tests-impl is a coverage step, not a behavior-implementing step").

Capture the test id + first 2-3 lines of output for `tdd_red_evidence`. Per CLAUDE.md, `tests-impl` is a dedicated coverage step and is exempt from strict RED-first when the underlying code is already in place — in that case use `"n/a — coverage-only tests; underlying behaviour landed in S03"`.

## Project Conventions

- Match the existing `tests/integration/test_scope_amend_endpoints.py` fixture and assertion style.
- Use `assert event.event_metadata.get("matched_patterns") == [...]` not `assert "matched_patterns" in event.event_metadata` — strong assertions per `skills/iw-ai-core-testing/SKILL.md`.
- Group the four new tests under a clear class or section header so a reader can find them at a glance.

## TDD Requirement

For coverage tests added by `tests-impl`, the strict RED-first rule does not apply (the code being tested may already exist from S03). Capture either a real RED failure (when running before S03 lands) or write `"n/a — coverage-only tests; underlying behaviour landed in S03"` in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`**
2. **`make typecheck`**
3. **`make lint`**

## Test Verification (NON-NEGOTIABLE)

Run only the test file you modified:

```bash
uv run pytest tests/integration/test_scope_amend_endpoints.py -v
```

Do NOT run `make test-integration` — that is the S13 QV gate.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "tests-impl",
  "work_item": "CR-00087",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_scope_amend_endpoints.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — coverage-only tests; underlying behaviour landed in S03",
  "blockers": [],
  "notes": ""
}
```
