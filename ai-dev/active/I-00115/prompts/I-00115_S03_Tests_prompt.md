# I-00115_S03_Tests_prompt

**Work Item**: I-00115 — Amend-scope modal locks the dashboard UI after dismissal
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy — no docker mutations, testcontainer fixtures exempt. Full text: see project's `CLAUDE.md` and `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item touches NO migrations. Do not run any `alembic` command. If you think you need to, STOP and raise a blocker.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00115 --json`
- `ai-dev/active/I-00115/I-00115_Issue_Design.md` — design document (READ FIRST)
- `ai-dev/active/I-00115/reports/I-00115_S01_Frontend_report.md` — S01 implementation report
- `ai-dev/active/I-00115/reports/I-00115_S02_CodeReview_report.md` — S02 review report
- `dashboard/templates/components/scope_amend_modal.html` — fixed template (post-S01)
- `tests/integration/test_scope_amend_endpoints.py` — existing scope-amend integration test; copy the fixture/seed pattern, do NOT modify it
- `tests/dashboard/conftest.py` — re-exports `db_session` from integration conftest
- Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` for assertion-strength rules

## Output Files

- `ai-dev/active/I-00115/reports/I-00115_S03_Tests_report.md` — step report
- New file: `tests/dashboard/test_scope_amend_modal_i00115.py` — reproduction + regression tests

## Context

You are writing the reproduction and regression tests for I-00115. The defect is in a Jinja2 template (`scope_amend_modal.html`); the test asserts on the rendered HTML returned by `GET /project/{id}/api/item/{item_id}/scope/amend-modal/{step_id}`.

The test file lives under `tests/dashboard/` (it drives a FastAPI route via TestClient, so per `tests/CLAUDE.md` it must NOT live under `tests/unit/`).

Read the design document's `## Test to Reproduce` section in full — it lists the exact assertions the two reproduction tests must make.

## Requirements

### 1. Create `tests/dashboard/test_scope_amend_modal_i00115.py`

Two reproduction tests are mandatory:

1. **`test_i00115_modal_submit_form_wires_cleanup_hook`** — Asserts that the `<form hx-post=".../scope/amend-and-restart/...">` open tag contains references to both `scope-amend-modal` AND `scope-amend-overlay`. The fix uses an `hx-on::after-request` attribute (or equivalent htmx idiom) that names both IDs. This test FAILS on pre-S01 HEAD (form open tag has neither ID) and PASSES on post-S01 HEAD.

2. **`test_i00115_modal_close_button_uses_getelementbyid_for_overlay`** — Asserts that the literal substring `this.closest('#scope-amend-overlay')` is NOT present anywhere in the modal HTML. This test FAILS on pre-S01 HEAD (line 22 has the broken pattern) and PASSES on post-S01 HEAD.

Three additional regression tests are mandatory:

3. **`test_i00115_modal_esc_key_dismisses`** — Asserts the rendered template wires up an ESC keydown handler. The handler can be inline (`onkeydown="..."` on the modal div) or a `<script>` block listening on `document` — your assertion should be tolerant of either approach (e.g. search for `'Escape'` OR `keyCode === 27` in the rendered HTML), but it MUST reference removing both `#scope-amend-modal` AND `#scope-amend-overlay` from the DOM.

4. **`test_i00115_modal_backdrop_click_dismisses`** — Asserts the `#scope-amend-overlay` div has a click handler. The handler must guard against clicks on child elements propagating (e.g. an `event.target === overlay` check, or attaching the listener only to the overlay's own click). Assert that the overlay element has either an `onclick="..."` attribute or that a `<script>` block contains an event listener bound to `getElementById('scope-amend-overlay')`.

5. **`test_i00115_cancel_button_still_works`** — Regression guard: the Cancel button (line 60 in pre-fix) was already correct; confirm it still uses `document.getElementById(...)` for BOTH `scope-amend-modal` AND `scope-amend-overlay`. This is a guard against a future refactor accidentally re-breaking Cancel.

### 2. Fixture pattern — reuse, do not invent

The test needs a scope-blocked step in the DB so the modal endpoint returns 200. Copy the seed helpers from `tests/integration/test_scope_amend_endpoints.py` — do NOT invent a new pattern. The TestClient fixture pattern (file-local `client` fixture) is also in that file. Per `tests/dashboard/conftest.py`, `db_session` is re-exported from the integration conftest, so you can depend on it directly.

### 3. CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "scope-amend-modal" in html` (substring match — false-positive against the modal's own ID attribute existing pre-fix too)
- BAD: `assert "overlay" in html` (always true — the overlay always renders, even with broken cleanup)
- GOOD: `assert "this.closest('#scope-amend-overlay')" not in html` (verifies the SPECIFIC broken pattern is gone)
- GOOD: assert the form open tag contains BOTH `scope-amend-modal` AND `scope-amend-overlay` (verifies cleanup wiring references both, not just one)
- GOOD: deleting the production fix line in the template MUST flip the test red

Apply the **mutation test question** from `skills/iw-ai-core-testing/SKILL.md` §0 to every assertion: *if I deleted the fix, would this test fail?* If the answer is no, the assertion is shape-checking — strengthen it.

### 4. RED phase — verify your tests would fail pre-fix

After writing the tests, do the following to confirm they are RED-first:

1. Run `git log --oneline --all -- dashboard/templates/components/scope_amend_modal.html | head -5` to see recent commits to the template.
2. Diff the post-S01 template against pre-S01 (`git diff main -- dashboard/templates/components/scope_amend_modal.html` or against the S01 base — pick the commit hash before S01's change from the log).
3. Reason explicitly: "if I applied this test against pre-S01 HEAD, would each assertion fail?" Write your reasoning into `tdd_red_evidence` (1-3 lines per test, citing the line numbers that violate the assertion in the pre-fix template).

Do NOT run `git stash` / `git checkout HEAD~1 -- ...` to revert source files at runtime — per `iw-new-incident` skill: that operation is thrash-prone and forbidden. The RED-first verification is by reasoning + diff inspection.

### 5. Test-file location and `client` fixture

- File: `tests/dashboard/test_scope_amend_modal_i00115.py`
- The test renders a Jinja2 template via FastAPI TestClient → must be in `tests/dashboard/`, NOT `tests/unit/`.
- Define a **file-local** `client` fixture (copy pattern from `tests/integration/test_scope_amend_endpoints.py` or another `tests/dashboard/test_*` file that exercises a router).
- `db_session` is auto-resolved via `tests/dashboard/conftest.py`'s re-export.

### 6. Test verification (NON-NEGOTIABLE)

Run ONLY the new test file:

```bash
uv run pytest tests/dashboard/test_scope_amend_modal_i00115.py -v
```

ALL five tests must pass against the post-S01 template. Do **NOT** run `make test-integration` or `make test-unit` — full-suite execution is owned by S11/S12 QV gates. Duplicating it here burns the step's timeout budget (see I-00073/S03 post-mortem).

## Project Conventions

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` in full. Key rules for this step:

- Live DB (port 5433) is OFF LIMITS — use testcontainer-backed `db_session` only.
- `importlib.reload(orch.config)` is FORBIDDEN — use `monkeypatch.delenv()` instead.
- Do NOT mock the database in this test — the modal endpoint reads real StepRun rows.
- Tests assert behaviour, not their own mocks. Every assertion must satisfy the mutation question.
- Use the attribute-scoped form for CSS class assertions: `'class="my-class"' in html`, not bare `'my-class' in html` (per I-00067).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`** — auto-fix.
2. **`make type-check`** — zero errors on the new test file.
3. **`make lint`** — zero errors.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00115",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_scope_amend_modal_i00115.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed",
  "tdd_red_evidence": "test_..._submit_form: pre-S01 form open tag (lines 40-41 of template) contains no 'scope-amend-modal' or 'scope-amend-overlay' references → assertion would fail. test_..._close_button: pre-S01 line 22 contains literal `this.closest('#scope-amend-overlay')` → assertion `not in html` would fail. test_..._esc: pre-S01 has no ESC handler → assertion would fail. test_..._backdrop: pre-S01 overlay is empty `<div>` → assertion would fail. test_..._cancel: pre-S01 cancel was already correct; this is a regression guard.",
  "blockers": [],
  "notes": "Which idiom S01 chose (hx-on::after-request vs <script> block) and how the assertions accommodate both."
}
```
