# I-00076_S03_Tests_prompt

**Work Item**: I-00076 -- Per-step CLI/runtime override `<select>` silently clears the override instead of setting it
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`,
`docker system|container|image prune`). Testcontainers spun up by pytest fixtures are the
allowed exception. Read-only `docker ps|inspect|logs` and `./ai-core.sh` / `make` targets are fine.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step writes tests only — no alembic migration. Do NOT run any alembic command.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00076 --json`
- `ai-dev/active/I-00076/I-00076_Issue_Design.md` -- the design doc. Read **Test to Reproduce**, **Acceptance Criteria** (AC1, AC2, AC3), **TDD Approach**, and **Notes**.
- `ai-dev/active/I-00076/reports/I-00076_S01_Frontend_report.md` and `…_S02_CodeReview_report.md` -- prior steps.
- `dashboard/templates/fragments/item_overview.html` -- the fixed template (the editable-step `<select>` with `hx-disabled-elt="this"`).
- `tests/dashboard/test_runtime_override_templates.py` -- **the existing test file for this exact surface**. Reuse its seed helpers (`_seed_runtime_options`, `_seed_project_and_batch`, `_seed_work_item_with_steps`) and its `client` fixture pattern. You may add your assertions here, or create a sibling `tests/dashboard/test_i00076_runtime_override_select.py` that imports/duplicates the minimal seed scaffolding — either is acceptable; prefer extending the existing file if it stays cohesive.
- `tests/dashboard/test_runtime_overrides_api.py` -- existing API tests for `patch_step_runtime_override`; reuse its patterns for the persistence test.
- `tests/dashboard/conftest.py` -- where the `db_session` (and possibly `client`) fixtures live. **Tests that render a template via the dashboard `client` or call a FastAPI route MUST live under `tests/dashboard/`** (the `client`/`db_session` fixtures are not available under `tests/unit/` or `tests/integration/` — I-00067).
- `dashboard/routers/runtime_overrides.py` -- the endpoint under test.
- `orch/agent_runtime/resolver.py` -- `resolve_runtime`, if you add the optional resolver assertion.
- `CLAUDE.md` + `tests/CLAUDE.md` -- test rules (testcontainers only for live-DB-shaped tests; the `db_session` fixture handles that; never connect to port 5433).

## Output Files

- `tests/dashboard/test_runtime_override_templates.py` (modified) **and/or** `tests/dashboard/test_i00076_runtime_override_select.py` (new) -- the tests
- `ai-dev/active/I-00076/reports/I-00076_S03_Tests_report.md` -- step report

## Context

The bug was client-side (htmx form serialisation), so the reproduction test is a **template-render assertion** plus a **server-side persistence assertion**. Both must fail against pre-fix code and pass after.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Apply this here: don't just assert "the `<select>` is present" — assert the *corrected* markup is present and the *broken* markup is absent; don't just assert "the PATCH returned 204" — assert `workflow_steps.agent_runtime_option_id` holds the *exact* chosen id afterwards.

## Requirements

### 1. Reproduction test — corrected `<select>` markup (template render)

Add a test (suggested name `test_i00076_editable_step_select_uses_hx_disabled_elt`) that:
- Seeds a project + work item with at least one `WorkflowStep` in `failed` (and ideally one in `pending`) status, plus the runtime option rows (reuse `_seed_runtime_options`).
- GETs `/project/{project_id}/item/{item_id}/tab/overview`.
- Asserts (attribute-anchored — per I-00067, anchor on `attr="value"`, not a bare token, so a stray token in a script/comment can't false-positive):
  - `assert 'hx-disabled-elt="this"' in html`
  - `assert "this.disabled=true" not in html` and `assert "this.disabled = true" not in html`
  - `assert "htmx.trigger(this" not in html`
  - `assert f'hx-patch="/project/{project_id}/api/item/{item_id}/step/{step_id}/runtime-override"' in html` (the PATCH wiring survives)
  - `assert 'name="option_id"' in html`
- This test FAILS against pre-fix `item_overview.html` (which has `this.disabled=true` / `htmx.trigger(this, 'change')` and no `hx-disabled-elt`) and PASSES after S01.

### 2. Persistence test — `patch_step_runtime_override` (route)

Add a test (suggested name `test_i00076_patch_step_override_persists_and_clears`) that, given a `failed` step and an enabled `AgentRuntimeOption` (e.g. id 5 — `cli_tool="claude"`, `model="claude-opus-4-7"` — use the seed helper's IDs):
- PATCH `/project/{project_id}/api/item/{item_id}/step/{step_id}/runtime-override` with form `option_id=5` → asserts `204` AND `db_session.refresh(step); assert step.agent_runtime_option_id == 5`.
- PATCH the same endpoint with **no body** → asserts `204` AND `step.agent_runtime_option_id is None` (the `— inherit —` / clear path — AC3).
- (If `test_runtime_overrides_api.py` already covers part of this, extend rather than duplicate; ensure at minimum the "valid id is persisted" assertion exists and is semantic.)

### 3. (Optional but recommended) Resolver assertion — `resolve_runtime`

If it fits cleanly without a heavy fixture, add a small test that with `workflow_steps.agent_runtime_option_id` pointing at the `claude`/`claude-opus-4-7` row, `resolve_runtime(...)` returns **that exact row** — `assert resolved.cli_tool == "claude" and resolved.model == "claude-opus-4-7"` — i.e. the step override wins over the project default. Skip only if it would require disproportionate scaffolding; note the decision in your report.

### 4. Naming, isolation, conventions

- Test names start with `test_i00076_` so they're traceable to this incident.
- No live-DB connection (the `db_session` fixture is testcontainer-backed or the dashboard test fixture — use it; never reference port 5433).
- Match the existing file's structure, imports, and fixture usage. Keep new seed scaffolding minimal — reuse `_seed_*` helpers.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting completion: `make format`, then `make typecheck` (zero errors in files you touched), then `make lint`. Populate `preflight`.

## Test Verification (NON-NEGOTIABLE)

Run **only the test file(s) you wrote/modified**:
```bash
uv run pytest tests/dashboard/test_runtime_override_templates.py -v
# and, if you added a sibling file:
uv run pytest tests/dashboard/test_i00076_runtime_override_select.py -v
```
Do **NOT** run `make test-integration`, `make test-unit`, or `make test-dashboard` — those are downstream QV gates (S11/S12) with their own budgets. Running them here is a known cause of step timeouts (I-00073/S03 post-mortem).

Do not report `tests_passed: true` unless your targeted tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/dashboard/test_runtime_override_templates.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Note whether the optional resolver test was added or skipped, and why."
}
```
