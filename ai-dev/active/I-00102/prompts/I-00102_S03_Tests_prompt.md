# I-00102_S03_Tests_prompt

**Work Item**: I-00102 — iw register silently ignores design-package drift; approve must auto-refresh workflow_steps
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

You do not touch migrations. Tests against the schema use the project's testcontainer fixtures (which apply `alembic upgrade head` automatically).

## Input Files

- **Runtime step state** — `uv run iw item-status I-00102 --json`.
- `ai-dev/active/I-00102/I-00102_Issue_Design.md` — design doc (read **Test to Reproduce**, **Acceptance Criteria** AC1–AC5, **TDD Approach** in full).
- `ai-dev/active/I-00102/reports/I-00102_S01_Database_report.md` and `…_S02_Backend_report.md` — to confirm column name, helper name/location, and approve flow shape.
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — testing conventions (read both — assertion-strength rules, live-DB write guard, testcontainer rules).
- `tests/integration/conftest.py` and `tests/conftest.py` — fixture catalogue (`pg_engine`, `db_session`, `test_project`).
- `orch/cli/item_commands.py` after S02 — to know the helper signature and the approve flow you're testing.

## Output Files

- `tests/integration/test_item_register_drift.py` — new, reproduction + regression tests.
- `tests/unit/test_item_commands_digest.py` — extend (S02 created this file with the determinism-across-key-order seed test; you add the rest of the digest invariants).
- `ai-dev/active/I-00102/reports/I-00102_S03_Tests_report.md` — step report.

## Context

S02 closed the bug in `iw register` / `iw approve`. Your job is to write the regression net so future refactors cannot silently re-open it. The reproduction test must be high-fidelity to the CR-00067 scenario (register → edit on disk → approve) and must FAIL against the pre-fix code (proving it would have caught the original bug).

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this incident specifically:

- BAD: `assert len(workflow_steps) > 0` after refresh — passes even when refresh did nothing.
- GOOD: `assert [s.step_id for s in workflow_steps] == ["S01", "S02", "S03"]` — verifies the exact post-refresh layout.
- BAD: `assert "manifest_refreshed" in event_types` — passes even if the event carries empty metadata.
- GOOD: `assert event.event_metadata["old_step_count"] == 2 and event.event_metadata["new_step_count"] == 3` — verifies the audit event names the actual change.

## Requirements

### 1. Unit tests — `tests/unit/test_item_commands_digest.py`

S02 seeded this file with the determinism-across-key-order test. Extend it with:

- `test_digest_is_deterministic_across_whitespace` — same logical steps with different JSON indentation (e.g. one written via `json.dumps(steps)` and one via `json.dumps(steps, indent=2)`, both parsed back into Python before hashing) → same digest. (The helper hashes Python dicts, not raw JSON, so this is really a sanity check that `parse_manifest_steps` normalises before the helper sees the data — assert through that.)
- `test_digest_changes_when_step_id_changes` — renumbering one step from `S02` to `S03` produces a different digest.
- `test_digest_changes_when_prompt_path_changes` — renaming a prompt from `prompts/X_S01_Backend.md` to `prompts/X_S01_NewBackend.md` produces a different digest.
- `test_digest_changes_when_step_added` — adding a new step changes the digest.
- `test_digest_changes_when_step_removed` — removing a step changes the digest.
- `test_digest_changes_when_steps_reordered` — same set, different order → different digest (order matters because step_number is positional).
- `test_digest_ignores_top_level_note_field` — only the steps array contributes; varying `_note` / `title` / `scope` does not affect the digest (call the helper with the SAME steps list but assert the helper signature doesn't accept top-level fields at all, which encodes the contract).
- `test_digest_ignores_none_and_empty_string_keys_inside_a_step` — a step dict with `{"step": "S01", "agent": "backend-impl", "prompt": None, "command": ""}` produces the same digest as `{"step": "S01", "agent": "backend-impl"}` (the helper drops empty values during canonicalization).

Each test must assert specific digest equality or inequality — never just "truthy" / "length > 0".

### 2. Integration tests — `tests/integration/test_item_register_drift.py`

Uses the standard `db_session` + `test_project` testcontainer fixtures. The flow exercises the CLI by calling the `register`/`approve` Click commands directly with a configured Click context — see `tests/integration/test_dashboard_remaining.py` or `tests/integration/test_chat_tabs_api.py` for the ctx-construction pattern used elsewhere in this suite. (Subprocessing the real `iw` binary is also acceptable if you wire it through the existing pattern; pick one and be consistent.)

Required tests:

- **`test_approve_auto_refreshes_workflow_steps_when_manifest_drifted_after_register`** — the canonical reproduction (mirrors design **Test to Reproduce** verbatim):
  1. Write design + 2-step manifest v1 (S01 Backend, S02 qv-gate unit-tests) under a temp `ai-dev/active/<item_id>/` rooted at the test project's repo_root (use a `test-` prefix item_id like `I-99102` to never collide with real sequence).
  2. Call `register`. Assert exit 0; query `workflow_steps`: exactly `["S01", "S02"]`, agent_labels exactly `["Backend", "QvGate"]`.
  3. Snapshot `item.manifest_digest` (must be non-NULL, sha256 hex length 64).
  4. Edit manifest in place to 3-step v2 (S01 Database, S02 Backend, S03 qv-gate unit-tests). Rename / add prompt files on disk to match. Do NOT re-run register.
  5. Call `approve`. Assert exit 0.
  6. Query `workflow_steps` again: exactly `["S01", "S02", "S03"]`, agent_labels exactly `["Database", "Backend", "QvGate"]`.
  7. Query `daemon_events`: exactly one `manifest_refreshed` event for this item, with `event_metadata["old_step_count"] == 2`, `event_metadata["new_step_count"] == 3`, `event_metadata["trigger"] == "approve"`, and `event_metadata["old_digest"] != event_metadata["new_digest"]`.
  8. Assert `item.manifest_digest` now equals the v2 digest (compute via the same helper for parity).
  9. Assert `item.status == approved`.

- **`test_approve_no_drift_does_not_emit_refresh_event`** — happy path:
  1. Register manifest v1; approve immediately (no edits).
  2. Assert exit 0, status approved, AND no `manifest_refreshed` event for this item in `daemon_events`.

- **`test_register_stores_initial_digest`** — after register, `WorkItem.manifest_digest` is non-NULL and equals `_compute_manifest_digest(parse_manifest_steps(manifest_path))`.

- **`test_approve_with_null_digest_treats_as_drift_and_refreshes`** — backfill safety (AC5):
  1. Register normally so the row is created.
  2. UPDATE the row directly to set `manifest_digest = NULL` (simulating a pre-fix legacy row).
  3. Approve. Assert: refresh runs (one `manifest_refreshed` event, `event_metadata["old_digest"] is None`), digest is now populated, status approved.

- **`test_approve_with_missing_manifest_fails_loudly`** — error path:
  1. Register. Delete the on-disk `workflow-manifest.json`. Approve. Assert: exit non-zero, error message names the missing path, no `workflow_steps` rows were touched, no `manifest_refreshed` event recorded, status remains `draft`.

- **`test_approve_drift_rebuild_is_atomic_on_failure`** — transaction safety. Monkeypatch `parse_manifest_steps` to raise after the existing rows would have been deleted, simulating a mid-rebuild crash. Approve. Assert: the transaction rolled back — original `workflow_steps` rows are intact (count and agent_labels unchanged), `item.manifest_digest` unchanged, status unchanged, no `manifest_refreshed` event recorded.

### 3. Test isolation & live-DB rules

- NEVER connect to the live DB (port 5433). Use the testcontainer-backed `db_session` fixture only.
- NEVER mock the DB — `FOR UPDATE` locking and the in-transaction rebuild can only be exercised against a real Postgres.
- Use the `tmp_path` fixture for the on-disk `ai-dev/active/<item_id>/` scaffolding. Monkeypatch the working directory or the resolver so the CLI commands find the temp tree.
- Use `monkeypatch.delenv` (not `importlib.reload`) for any env-var manipulation.
- Item IDs in these tests MUST be in the `I-99NNN` reserved range (per the project's test-id convention — see `tests/CLAUDE.md` / cross-project isolation section).

### 4. Mutation-test check (every assertion must be able to fail)

For each assertion, ask: "if the production code regressed in the obvious way (e.g. delete the `manifest_digest = new_digest` line; remove the `DaemonEvent` insert; flip the `delete()` to do nothing), would this test catch it?" If the answer is "no", strengthen or delete the assertion. The reproduction test must catch the **silent no-op** that produced CR-00067/S08 — that is the bug-shaped regression.

## Project Conventions

Read `tests/CLAUDE.md` for fixture rules, the FTS trigger requirement, the live-DB write guard, the per-test template-clone strategy (pytest-randomly is ON by default), and quarantine policy. Read `skills/iw-ai-core-testing/SKILL.md` for the assertion-strength rules and the test red-flag checklist.

## TDD Requirement (tests step)

This step IS the test layer — the "RED then GREEN" cycle ran across S01+S02. Your job is to make the regression net robust:

- The reproduction test (`test_approve_auto_refreshes_workflow_steps_when_manifest_drifted_after_register`) MUST be runnable against the pre-fix code and fail. You do **not** need to revert source at runtime to prove this; trust that S02's GREEN run + your new test's GREEN run jointly prove the contract. (Per template: design-time RED is the human authoring the design's job; runtime revert is thrash-prone and prohibited.)
- Use `tdd_red_evidence: "n/a — dedicated test-coverage step"` in your result contract.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Run only the new test files:

```bash
uv run pytest tests/unit/test_item_commands_digest.py tests/integration/test_item_register_drift.py -v
```

Do NOT run `make test-unit` or `make test-integration`. S12/S13 own those.

## Subagent Result Contract

```bash
mkdir -p ai-dev/active/I-00102/reports
uv run iw step-done I-00102 --step S03 \
  --report ai-dev/active/I-00102/reports/I-00102_S03_Tests_report.md
```

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00102",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_item_commands_digest.py",
    "tests/integration/test_item_register_drift.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "tests/unit/test_item_commands_digest.py: N passed; tests/integration/test_item_register_drift.py: M passed",
  "tdd_red_evidence": "n/a — dedicated test-coverage step",
  "blockers": [],
  "notes": ""
}
```

If FAILED: `uv run iw step-fail I-00102 --step S03 --reason "..."`.

**IMPORTANT**: Call `step-done` or `step-fail` before exiting.
