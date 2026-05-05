# I-00067_S05_CodeReview_Final_prompt

**Work Item**: I-00067 -- Recent Activity messages need truncation + click-to-expand popup
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item adds NO migrations — verify the diff confirms this.

## Input Files

- `uv run iw item-status I-00067 --json` — runtime step state
- `ai-dev/active/I-00067/I-00067_Issue_Design.md` — Design document
- All implementation step reports under `ai-dev/active/I-00067/reports/I-00067_S0{1,3}_*_report.md`
- All per-agent code review reports under `ai-dev/active/I-00067/reports/I-00067_S0{2,4}_CodeReview_report.md`
- All files listed in S01 + S03 `files_changed`

## Output Files

- `ai-dev/active/I-00067/reports/I-00067_S05_CodeReview_Final_report.md`

## Context

You are performing the final cross-agent review of all implementation work for I-00067 — Recent Activity messages need truncation + click-to-expand popup. Your job is to catch cross-cutting issues per-agent reviews could not.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Report new violations as CRITICAL findings.

## Review Checklist

### 1. Completeness vs Design Document

- AC1 (long messages → 100 + `...`) — covered by S01 (template change) and S03 tests?
- AC2 (short messages render verbatim with NO `...` and NO affordance) — covered?
- AC3 (popup opens, ESC / outside-click / close button dismiss, focus returns) — covered? Browser verification (S14) will confirm; this review confirms the code paths exist.
- AC4 (regression test exists and is falsifiable on main) — confirmed?

If any acceptance criterion has no corresponding implementation or test, that is a CRITICAL finding (`missing_requirements`).

### 2. Cross-Agent Consistency

- Does the trigger class name in S01 match what S03 asserts on?
- Does the `data-full-text` attribute name (or whichever payload pattern S01 chose) match what S03 asserts on?
- Does the modal partial's element ID set match what the JS click handler queries?

### 3. Integration Points

- The new modal partial is included from the project dashboard template — verify by `grep` for the `{% include %}` directive.
- The JS click handler attaches at `DOMContentLoaded` or as a delegated listener — confirm it works regardless of when truncated rows appear.
- The modal's `<script>` block is loaded once even when the partial is included from a single page (no double-binding).

### 4. No regressions

- Run `make test-integration` AND `make test-unit`. Existing dashboard tests pass:
  - `tests/integration/test_dashboard_pages.py::test_project_dashboard_returns_200`
  - `tests/integration/test_dashboard_pages.py::test_recent_activity_batch_event_links_to_batch_route`
  - `tests/integration/test_dashboard_pages.py::test_recent_activity_doc_job_event_links_to_doc_job_route`
  - `tests/integration/test_dashboard_pages.py::test_recent_activity_work_item_event_links_to_item_route`
  - `tests/integration/test_dashboard_pages.py::test_recent_activity_unknown_entity_type_falls_back_to_item_route`
  - `tests/integration/test_dashboard_pages.py::test_recent_activity_no_link_renders_when_entity_id_is_null`

### 5. Architecture Compliance

- New partial lives under `dashboard/templates/fragments/` and does NOT extend `base.html`.
- No new Python helpers added under `orch/` (this is a template-only change).
- Tailwind CSS is regenerated via `make css` if new utility classes were used.
- Read `dashboard/CLAUDE.md` and `CLAUDE.md` for conformance.

### 6. Security

- Modal body is populated via `textContent`, not `innerHTML`. Confirm by reading the JS source.
- `data-full-text` attribute uses Jinja2's autoescape — no `|safe`, no `Markup(...)`.
- Test `test_html_in_message_is_escaped_in_both_preview_and_payload` exists and passes.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
```

Both must pass with zero failures. Integration test failures are CRITICAL.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00067",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
