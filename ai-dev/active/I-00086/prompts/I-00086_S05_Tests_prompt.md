# I-00086_S05_Tests_prompt

**Work Item**: I-00086 -- Runtime override controls give no UI feedback
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures spun up by pytest are exempt and required.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this work item.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00086 --json`.
- `ai-dev/active/I-00086/I-00086_Issue_Design.md` — design document (READ FIRST; specifically the **TDD Approach** and **Acceptance Criteria** sections)
- `ai-dev/active/I-00086/reports/I-00086_S01_API_report.md` — S01 step report
- `ai-dev/active/I-00086/reports/I-00086_S03_Frontend_report.md` — S03 step report
- `dashboard/routers/runtime_overrides.py` — updated by S01
- `dashboard/templates/fragments/item_overview.html` — updated by S03
- `dashboard/templates/fragments/item_steps_table.html` — new in S03
- `tests/dashboard/conftest.py` — the `client` fixture and any item/workflow-step factory fixtures
- `tests/CLAUDE.md` — testing rules and fixture conventions

## Output Files

- `ai-dev/active/I-00086/reports/I-00086_S05_Tests_report.md` — Step report
- New / updated test file(s) under `tests/dashboard/`

## Context

You write the **reproduction test** and **regression test suite** for **I-00086**. The fix has already been implemented by S01 (API) and S03 (Frontend). Your tests must:

1. Prove the bug existed (would fail against pre-fix HEAD).
2. Confirm the fix works (pass against current HEAD).
3. Protect against future regressions (assert specific response values, not just status codes).

The test file lives under `tests/dashboard/` because it drives FastAPI routes via the `client` fixture, which is registered ONLY in `tests/dashboard/conftest.py`. A test placed in `tests/unit/` or `tests/integration/` will fail with `fixture 'client' not found` (I-00067).

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "showToast" in trigger` (shape only)
- GOOD: `assert trigger["showToast"]["message"] == "Model updated for 3 step(s)"` (semantic — verifies specific expected value)
- GOOD: `assert trigger["showToast"]["type"] == "success"` (semantic)
- BAD: `assert "HX-Trigger" in resp.headers`
- GOOD: `parsed = json.loads(resp.headers["HX-Trigger"]); assert parsed == {...}`

Every assertion in this test file must capture a specific expected value, not just "something is there".

## Requirements

### 1. Reproduction test (AC4)

Create `tests/dashboard/test_runtime_override_response.py` (or extend an existing `test_runtime_overrides*.py` if one exists — check first with `ls tests/dashboard/ | grep runtime`).

Include at minimum the `test_i00086_bulk_apply_returns_fragment_and_toast_trigger` test from the design document's **Test to Reproduce** section. It must:

- Use the dashboard `client` fixture.
- Set up an item with **at least 2 editable (pending) steps** + at least one enabled `agent_runtime_options` row.
- Call `PATCH /project/{project_id}/api/item/{item_id}/runtime-override/bulk` with `data={"option_id": ...}`.
- Assert `resp.status_code == 200`.
- Assert `'id="item-steps-table"' in resp.text`.
- Parse `resp.headers["HX-Trigger"]` as JSON; assert `parsed["showToast"]["type"] == "success"` AND `parsed["showToast"]["message"] == f"Model updated for {N} step(s)"` where N is the number of editable steps you seeded.

### 2. Per-step success path

Test `test_per_step_override_returns_fragment_and_toast_trigger`:

- Seed an item with at least one `pending`/`failed` step.
- Call `PATCH /project/{project_id}/api/item/{item_id}/step/{step_id}/runtime-override` with form-encoded `option_id=<id>`.
- Assert `resp.status_code == 200`.
- Assert `'id="item-steps-table"' in resp.text`.
- Assert `resp.headers["HX-Trigger"]` parses to `{"showToast": {"message": "Model updated", "type": "success"}}` (exact equality).
- Assert the rendered fragment contains the **updated** model label for that step (semantic: the new option's `model_label` MUST appear in the response body inside an HTML attribute or cell, not as raw substring inside a comment).

### 3. Per-step "clear override" path (option_id = None / empty string)

Test `test_per_step_clear_override_returns_fragment_and_toast_trigger`:

- Same setup but post with `option_id=""` (or omit `option_id`) to clear the override.
- Assert 200 + same fragment shape + same success toast.
- Assert the step's `agent_runtime_option_id` is now NULL in the DB (re-fetch via the session fixture).

### 4. Bulk zero-eligible-steps branch (AC3)

Test `test_bulk_apply_with_zero_editable_steps_returns_info_toast`:

- Seed an item where ALL steps are in a non-editable status (e.g. `done` or `in_progress` — pick whatever the existing factory makes easy).
- Call the bulk PATCH endpoint with any valid `option_id`.
- Assert `resp.status_code == 200`.
- Assert `'id="item-steps-table"' in resp.text`.
- Assert `resp.headers["HX-Trigger"]` parses to `{"showToast": {"message": "No editable steps to update", "type": "info"}}` (exact equality — note `type` is `info`, NOT `warning` or `success`).
- Assert NO `DaemonEvent` with `event_type='runtime_override_changed'` was emitted (query the `daemon_events` table after the call).
- Assert NO step's `agent_runtime_option_id` changed.

### 5. Validation paths preserved

Tests `test_per_step_unknown_item_returns_404` and `test_bulk_unknown_option_returns_404`:

- Confirm that bad input still raises HTTP 404 with NO `HX-Trigger` header (no toast on validation failure).
- Assert `"HX-Trigger" not in resp.headers`.

### 6. Bulk-count correctness

Test `test_bulk_apply_counts_only_editable_steps`:

- Seed an item with 5 steps: 3 pending, 1 in_progress, 1 done.
- Call bulk PATCH.
- Assert the toast message is `"Model updated for 3 step(s)"` — NOT 5.
- Assert ONLY the 3 pending steps had `agent_runtime_option_id` mutated; the in_progress and done steps are untouched.

### 7. Fragment contains correct content after the change

Test `test_response_fragment_reflects_updated_options_per_row`:

- Seed an item with 2 pending steps and >=2 runtime options.
- Call bulk PATCH with option B (different from each step's current option A).
- Assert the response body contains the model_label of option B in a cell context (not as a comment): grep with attribute-scoped regex/substring, e.g. `'<span class="text-xs text-muted-foreground">{model_label_B}</span>'`. Use the attribute-scoped form per `tests/CLAUDE.md`.
- Assert option A's label does NOT appear next to either step in the response body (use a tighter assertion than bare substring — verify by row).

## Project Conventions

Read `tests/CLAUDE.md`. Key rules for this work:

- Use the `client` fixture from `tests/dashboard/conftest.py` (FastAPI TestClient).
- Use the `db_session` (or equivalent) fixture for DB setup and post-call inspection.
- Use the testcontainer Postgres (NEVER live DB on port 5433).
- After `Base.metadata.create_all()`, ensure `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` are applied — the fixture handles this; do NOT call them yourself.
- `DaemonEvent.metadata` is named `event_metadata` in Python (SQLAlchemy reservation).
- `monkeypatch.delenv()` for env vars; NEVER `importlib.reload(orch.config)`.

## TDD Requirement

Follow RED-GREEN-REFACTOR:

1. **RED**: Write each test. Run only the new test file. Confirm any test that pinned `status_code == 204` on pre-fix code would fail now. If S01/S03 are already merged in this worktree, your tests should pass GREEN immediately — that's expected and correct.
   - To prove the RED phase: at design-time (not at run-time) the human authoring this design ran the failing test against pre-fix HEAD and confirmed it failed. You do NOT need to `git checkout HEAD~1` or `git stash` to re-prove this; document in `tdd_red_evidence` that the RED was verified by the design-doc author.
2. **GREEN**: Tests pass against the current (post-fix) code.
3. **REFACTOR**: Extract shared fixtures if you find yourself repeating seed code.

## Targeted Test Verification (NON-NEGOTIABLE)

Run ONLY the file you wrote/modified:

```bash
uv run pytest tests/dashboard/test_runtime_override_response.py -v
```

Do **NOT** call `make test-integration` or `make test-unit` — full-suite execution is owned by the downstream QV gates (`unit-tests`, `integration-tests`). Duplicating it inside the Tests step routinely blows the step's timeout budget (see I-00073/S03 post-mortem, 2026-05-08).

Do **NOT** revert source files at runtime to re-prove the RED — the RED proof is design-time, not run-time.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck   # zero new errors in your test file
make lint        # zero errors
```

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "I-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_runtime_override_response.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "7 passed, 0 failed",
  "tdd_red_evidence": "n/a — coverage step. RED for these endpoints was verified design-time by the human author against pre-fix HEAD.",
  "blockers": [],
  "notes": ""
}
```
