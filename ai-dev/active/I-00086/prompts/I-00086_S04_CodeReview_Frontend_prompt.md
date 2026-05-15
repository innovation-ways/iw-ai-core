# I-00086_S04_CodeReview_Frontend_prompt

**Work Item**: I-00086 -- Runtime override controls give no UI feedback
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy. No state-changing docker commands.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this work item.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00086 --json`.
- `ai-dev/active/I-00086/I-00086_Issue_Design.md` — design document
- `ai-dev/active/I-00086/reports/I-00086_S03_Frontend_report.md` — S03 step report
- All files listed in S03's `files_changed`

## Output Files

- `ai-dev/active/I-00086/reports/I-00086_S04_CodeReview_report.md` — Review report

## Context

You are reviewing the **template-extraction** and **htmx wiring** work done in S03. S03 should have:

1. Created `dashboard/templates/fragments/item_steps_table.html` containing the steps `<table>` + bulk-apply footer, wrapped with `id="item-steps-table"`.
2. Replaced the inline block in `fragments/item_overview.html` with `{% include "fragments/item_steps_table.html" %}`.
3. Added `hx-target="#item-steps-table"` + `hx-swap="outerHTML"` to BOTH the per-step `<select>` AND the bulk Apply button.
4. Preserved `hx-disabled-elt="this"` on the per-step `<select>` (CRITICAL — see design Notes section).
5. Kept the `<select id="bulk-runtime-option">` INSIDE the swapped fragment (so its `document.getElementById` lookup still resolves after a swap).

## Read the Design Document FIRST

Read `ai-dev/active/I-00086/I-00086_Issue_Design.md`. Specifically:

- **Acceptance Criteria** AC1, AC2, AC3.
- **Notes** — `hx-disabled-elt="this"` must be preserved; do NOT recommend `onchange="this.disabled=true"`.
- The constraint that no full page reload should happen (no `reload: true` in the toast trigger).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint           # ruff + node --check (dashboard JS) + scripts/check_templates.py
make format-check
```

Per `CLAUDE.md`: `scripts/check_templates.py` catches Jinja2 `format`-filter pitfalls (`%`-style required, never `str.format`-style). Any new violation in the changed templates is **CRITICAL**.

## Review Checklist

### 1. Template-Extraction Correctness

- Is `fragments/item_steps_table.html` a NEW file (not extending `base.html`)?
- Does it contain the full steps table AND the bulk-apply footer (selector + Apply button)?
- Every macro previously used in the inline block (`status_badge`, `approve_merge_button`, `restart_button`, `skip_button`, `kill_button`, `restart_merge_button`, `abandon_merge_button`, `restart_setup_button`) is imported / available in the new fragment?
- Every conditional branch from the original block is preserved? Run a side-by-side check between pre-fix `item_overview.html` and post-fix `item_steps_table.html` — no lost branches, no lost columns.
- The lazy-loaded `<div id="step-runs-{{ step.step_id }}" class="step-runs-container">` container is still rendered for steps with `run_count > 1`?
- The `<select id="bulk-runtime-option">` is INSIDE `item_steps_table.html` (so it survives the swap)?

### 2. htmx Wiring

- Per-step `<select>` has `hx-target="#item-steps-table"` AND `hx-swap="outerHTML"` AND **still** `hx-disabled-elt="this"`?
- Bulk Apply button has the same target/swap pair?
- The `hx-patch` URL paths are UNCHANGED?
- No `onchange="this.disabled=true"` JavaScript handler on the select (would clear the override — see design Notes)?
- The id used in `hx-target` (`#item-steps-table`) matches the id set on the rendered root element in `item_steps_table.html`?

### 3. Toast Hook Integration

- The page-level toast wiring in `dashboard/templates/pages/project/item_detail.html:158-167` was NOT modified by S03? (It already handles `HX-Trigger.showToast` from S01.)
- The new fragment does NOT add its own toast handling (would double-fire).

### 4. Project Conventions

- Tailwind classes used are ones that already appear in the codebase (so the prebuilt CSS covers them).
- No new dynamic class construction that breaks JIT purging.
- No clipboard buttons added (would need `iwClipboard.copy` per `dashboard/CLAUDE.md`).

### 5. Testing

- Did S03 run `tests/dashboard/` and report results?
- S05 (Tests) will cover dashboard assertions on the new fragment id; verify the design doc names this assertion explicitly.

### 5a. TDD RED Evidence

For template-only changes the RED evidence is template-level (curl/wget before vs. after, asserting `id="item-steps-table"`). The S03 report's `tdd_red_evidence` should be a plausible `"n/a — template-only ..."` narrative; if it claims a code-level RED that doesn't make sense for the change set, raise a **MEDIUM_FIXABLE**.

## Test Verification

```bash
uv run pytest tests/dashboard/ -v
```

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | `hx-disabled-elt` removed; bulk selector moved outside swap region; lost macro/branch from old template; `id` mismatch between target and rendered fragment |
| **HIGH** | Missing `hx-target`/`hx-swap` on one of the controls; new template extends `base.html`; new template has Jinja2 `format`-filter pitfall |
| **MEDIUM (fixable)** | Lint/format violations; missing comment about disabled-elt rule |
| **MEDIUM (suggestion)** | Better naming for the fragment id |
| **LOW** | Style nitpicks |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00086",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
