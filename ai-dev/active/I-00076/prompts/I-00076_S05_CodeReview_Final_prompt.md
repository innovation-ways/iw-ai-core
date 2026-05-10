# I-00076_S05_CodeReview_Final_prompt

**Work Item**: I-00076 -- Per-step CLI/runtime override `<select>` silently clears the override instead of setting it
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Testcontainers spun up by pytest fixtures are the allowed exception. Read-only `docker ps|inspect|logs`
and `./ai-core.sh` / `make` targets are fine.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration is in scope for I-00076. If any file under `orch/db/migrations/versions/**` was
added or modified across S01..S04, that is a CRITICAL out-of-scope finding.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00076 --json`
- `ai-dev/active/I-00076/I-00076_Issue_Design.md` -- design doc
- `ai-dev/active/I-00076/I-00076_Functional.md` -- functional doc
- `ai-dev/active/I-00076/reports/I-00076_S01_Frontend_report.md`
- `ai-dev/active/I-00076/reports/I-00076_S02_CodeReview_report.md`
- `ai-dev/active/I-00076/reports/I-00076_S03_Tests_report.md`
- `ai-dev/active/I-00076/reports/I-00076_S04_CodeReview_report.md`
- `dashboard/templates/fragments/item_overview.html` -- the changed template (diff vs `main`)
- `tests/dashboard/test_runtime_override_templates.py` and/or `tests/dashboard/test_i00076_runtime_override_select.py` -- the changed/new test(s) (diff vs `main`)
- `dashboard/routers/runtime_overrides.py`, `orch/agent_runtime/resolver.py` -- read-only; must be unchanged.

## Context

Final cross-agent review of I-00076. Per-agent reviews (S02, S04) already validated their own steps. Your job: catch issues that span the template change and the tests together, and confirm the whole package matches the design and is minimal.

Tiny surface — one template hunk + a few test functions. Focus on:
1. **Completeness vs design** — every Acceptance Criterion maps to code and/or a test assertion.
2. **Cross-step consistency** — the tests assert exactly the markup S01 produced (`hx-disabled-elt="this"` present; `this.disabled=true` and `htmx.trigger(this` absent), and the persistence test asserts the behaviour S01's fix enables.
3. **Scope discipline** — nothing outside `item_overview.html` (the editable `<select>`) and the test file(s) changed; the out-of-scope `w-24`→`w-48` / `cli_label`→`display_name` tweaks were NOT pulled in.
4. **No regression to the inherit path** — empty `option_id` still clears the override.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make format
make lint
```
Any NEW violation in the changed files (vs `main`) is a CRITICAL `conventions` finding. If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs design document

- [ ] `item_overview.html`: the editable-step `<select>` (the `{% elif step.status in ('pending','failed') %}` branch) carries `hx-disabled-elt="this"` and has NO `onchange` disabling it and NO `htmx.trigger(`. A clarifying comment is present.
- [ ] AC1 (bug fixed) — the markup change makes `option_id` serialisable; the persistence test confirms `agent_runtime_option_id` is set to the chosen id.
- [ ] AC2 (regression test exists) — the template-render test pins the corrected markup; it would fail against pre-fix HTML.
- [ ] AC3 (inherit path) — a test confirms PATCH with no `option_id` clears the override.

### 2. Cross-step consistency — template vs tests

- [ ] The exact strings the test asserts present (`hx-disabled-elt="this"`) and absent (`this.disabled=true`, `htmx.trigger(this`) match what S01 actually wrote (or didn't). No drift between what's rendered and what's asserted.
- [ ] The persistence test uses an `AgentRuntimeOption` id that the seed helper actually creates and that is `enabled` (otherwise `_validate_option_id` would 404).
- [ ] If the optional `resolve_runtime` test exists, the `(cli_tool, model)` pair it asserts matches the option row it set on the step.

### 3. Scope / minimality

- [ ] Only `dashboard/templates/fragments/item_overview.html` and `tests/dashboard/test_runtime_override_templates.py` (and/or the new `tests/dashboard/test_i00076_runtime_override_select.py`) changed. Anything else changed across S01..S04 is a CRITICAL out-of-scope finding.
- [ ] `class="… w-24"` unchanged; option text still `{{ opt.cli_label }}`. Presence of `w-48` / `display_name` is a HIGH out-of-scope finding.
- [ ] No `.py` under `orch/` or `dashboard/routers/` changed. No new Tailwind classes (no `make css` dependency).

### 4. Behavioural soundness

- [ ] Reason through: `<select>` + default `change` trigger + `hx-disabled-elt="this"` → htmx serialises `option_id` before disabling → PATCH carries the value → endpoint persists it → single request. If you can find a path where the value is still dropped, that's CRITICAL.
- [ ] No new console-error risk introduced (no broken inline JS left behind).

## Report

Write `ai-dev/active/I-00076/reports/I-00076_S05_CodeReview_Final_report.md` with a findings table and an overall verdict (`approve` / `request_changes`). Approve only with no CRITICAL/HIGH findings.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00076",
  "review_target": "S01..S04",
  "verdict": "approve|request_changes",
  "findings": [
    {"severity": "critical|high|medium|low", "category": "completeness|consistency|scope|conventions", "location": "file:NN", "description": "...", "recommendation": "...", "cross_cutting": true}
  ],
  "preflight": {"format": "ok|fixed", "lint": "ok"},
  "notes": ""
}
```
