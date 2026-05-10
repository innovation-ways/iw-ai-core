# I-00076_S04_CodeReview_Tests_prompt

**Work Item**: I-00076 -- Per-step CLI/runtime override `<select>` silently clears the override instead of setting it
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Testcontainers spun up by pytest fixtures are the allowed exception. Read-only `docker ps|inspect|logs`
and `./ai-core.sh` / `make` targets are fine.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

S03 writes tests only — no migration in scope. If S03 generated a migration, flag it CRITICAL.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00076 --json`
- `ai-dev/active/I-00076/I-00076_Issue_Design.md` -- design doc. **Read § Test to Reproduce, § Acceptance Criteria, § TDD Approach BEFORE the test code.**
- `ai-dev/active/I-00076/reports/I-00076_S03_Tests_report.md` -- S03's report
- `tests/dashboard/test_runtime_override_templates.py` and/or `tests/dashboard/test_i00076_runtime_override_select.py` -- the test code S03 wrote (review the diff vs `main`)
- `tests/dashboard/test_runtime_overrides_api.py` -- existing API tests, for comparison/overlap
- `dashboard/templates/fragments/item_overview.html`, `dashboard/routers/runtime_overrides.py`, `orch/agent_runtime/resolver.py` -- the code under test (read-only)

## Output Files

- `ai-dev/active/I-00076/reports/I-00076_S04_CodeReview_report.md` -- review report

## Context

You are reviewing the test coverage S03 produced. The key question: **would these tests have caught the bug?** A test that only checks "a `<select>` is present" would NOT — pre-fix code also rendered a `<select>`. The tests must assert the *corrected* markup is present AND the *broken* markup is absent, and that a valid `option_id` is actually persisted.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading the diff: `make format`, then `make lint`. Any NEW violation in the test files S03 touched is a CRITICAL `conventions` finding.

## Review Checklist

### 1. Reproduction test correctly targets the bug — semantic, not shape (I003)

- There is a template-render test that asserts ALL of: `'hx-disabled-elt="this"' in html`; `"this.disabled=true" not in html` (and the spaced variant); `"htmx.trigger(this" not in html`; the `hx-patch=".../runtime-override"` wiring is still present; `name="option_id"` is still present. — Missing any of these "negative" assertions (the `not in` ones) is a HIGH finding: the test wouldn't fail against pre-fix code.
- The assertions are **attribute-anchored** (`'hx-disabled-elt="this"'`, not a bare `hx-disabled-elt`) per the I-00067 CSS/attribute-scoping rule. Bare-substring assertions on rendered HTML are a MEDIUM finding.
- Confirm (by reasoning, not by reverting source) that the template test FAILS against pre-fix `item_overview.html`. If you can't convince yourself it would fail pre-fix, that's a HIGH finding.

### 2. Persistence test verifies the override is actually set

- A test PATCHes `…/step/{step_id}/runtime-override` with a real `option_id` and asserts the step row's `agent_runtime_option_id` equals **that exact id** afterwards (not just that the response is 204). — A shape-only check (just `assert resp.status_code == 204`) is a HIGH finding.
- A test PATCHes with no body and asserts the override is cleared (`agent_runtime_option_id is None`) — covers AC3. — MEDIUM if missing.
- If the optional `resolve_runtime` test exists, it asserts the *specific* resolved `(cli_tool, model)` pair, not merely that a row is returned.

### 3. Test hygiene

- Test names are traceable to the incident (`test_i00076_*`).
- Tests live under `tests/dashboard/` (not `tests/unit/` or `tests/integration/`) since they use the dashboard `client`/`db_session` fixtures — a misplaced test would error with `fixture not found` (I-00067).
- No live-DB connection (port 5433); the `db_session` fixture is used.
- Seed scaffolding reuses the existing `_seed_*` helpers rather than re-inventing; no copy-pasted bloat.
- Imports organised; no unused imports; no `print()`.

### 4. Coverage adequacy vs the design's Acceptance Criteria

- AC1 (bug fixed): covered by the template test + persistence test together.
- AC2 (regression test exists): the template test is the regression guard.
- AC3 (inherit path still works): covered by the "PATCH with no body clears" test.
- If any AC is uncovered, that's a HIGH finding (state which AC and what test is needed).

## Report

Write `ai-dev/active/I-00076/reports/I-00076_S04_CodeReview_report.md` with a findings table and a verdict (`approve` / `request_changes`). Approve only with no CRITICAL/HIGH findings.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00076",
  "review_target": "S03",
  "verdict": "approve|request_changes",
  "findings": [
    {"severity": "critical|high|medium|low", "category": "coverage|correctness|conventions", "location": "tests/dashboard/test_...py:NN", "description": "...", "recommendation": "..."}
  ],
  "preflight": {"format": "ok|fixed", "lint": "ok"},
  "notes": ""
}
```
