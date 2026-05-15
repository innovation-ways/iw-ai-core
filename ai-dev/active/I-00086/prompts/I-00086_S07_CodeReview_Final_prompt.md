# I-00086_S07_CodeReview_Final_prompt

**Work Item**: I-00086 -- Runtime override controls give no UI feedback
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

Standard policy. No state-changing docker commands.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this work item.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00086 --json`.
- `ai-dev/active/I-00086/I-00086_Issue_Design.md` — design document
- `ai-dev/active/I-00086/reports/I-00086_S0*_*_report.md` — all step reports from S01 through S06
- All files listed across all S01..S05 `files_changed` arrays

## Output Files

- `ai-dev/active/I-00086/reports/I-00086_S07_CodeReview_Final_report.md` — Final review report

## Context

You are performing the **final cross-agent review** for **I-00086 — runtime override controls give no UI feedback**. Per-agent reviews S02, S04, S06 have already shipped; your job is to verify the pieces fit together as one coherent fix and that the bug is actually fixed end-to-end.

## Read the Design Document FIRST

Read `ai-dev/active/I-00086/I-00086_Issue_Design.md`. Specifically:

- All four **Acceptance Criteria** (AC1, AC2, AC3, AC4).
- The **Test to Reproduce** section names a specific test by name; confirm S05's `files_changed` includes a file with that test.
- The **Notes** section's `hx-disabled-elt="this"` constraint.
- The **Impacted Paths** section — every modified file should fall inside one of these globs (the merge-time scope gate enforces this).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation across S01..S05 files is a **CRITICAL** finding with `category: "conventions"`.

## Review Checklist

### 1. End-to-End Coherence

- Does the URL path in the per-step `<select>`'s `hx-patch` match exactly what S01's `patch_step_runtime_override` is registered at?
- Does the URL path in the bulk button's `hx-patch` match exactly `patch_bulk_runtime_override`'s route?
- Does the id used in the template's `hx-target="#item-steps-table"` match the id rendered by the API's fragment? (If S01 took the fallback approach and returned `item_overview.html`, did S03 reconcile that?)
- Does the toast hookup in `item_detail.html:158-167` correctly read the JSON shape S01 emits (`HX-Trigger: {"showToast": {"message": "...", "type": "..."}}`)?

### 2. Completeness vs Design Document

- All three behavior changes from the design are present: per-step success toast, bulk success toast with count, bulk zero-eligible info toast.
- S05's test file contains the four named scenarios from the TDD Approach section.
- The exact test name from **Test to Reproduce** (`test_i00086_bulk_apply_returns_fragment_and_toast_trigger`) exists.

### 3. Cross-Agent Consistency

- The toast message strings are identical between the API code (S01) and the test assertions (S05):
  - `"Model updated for {N} step(s)"` for bulk success.
  - `"Model updated"` for per-step.
  - `"No editable steps to update"` for bulk zero.
- The toast `type` values are identical: `"success"` for success paths, `"info"` for zero-eligible.

### 4. Integration Points

- The `<select id="bulk-runtime-option">` lives INSIDE the swapped fragment (so its `getElementById` lookup survives the swap)?
- No double-fire: nothing in the new template inserts its own client-side toast handler that would compete with the page-level one in `item_detail.html`.
- No new code path bypasses `emit_runtime_override_changed` — the audit trail still works.
- Validation 404s do NOT carry `HX-Trigger` (would render an empty toast).

### 5. Architecture Compliance

- Routers stayed thin (per `dashboard/CLAUDE.md`); render helper lives in a sensible location.
- Fragment templates don't extend `base.html`.
- No new dependencies added; no Tailwind utility classes that aren't already covered by the prebuilt CSS.

### 6. Security (Cross-Cutting)

- No user input flows into the `HX-Trigger` JSON without being constrained to known constants (the message strings are hard-coded except for the `N` integer, which is a `len()` — safe).
- No secrets or credentials introduced.
- No log statement dumps `option_id` or runtime configuration unsanitized.

### 7. Scope Compliance

Every file modified across S01..S05 must fall inside the manifest's `scope.allowed_paths`:

- `dashboard/routers/runtime_overrides.py`
- `dashboard/templates/fragments/item_overview.html`
- `dashboard/templates/fragments/item_steps_table.html`
- `tests/dashboard/**`
- `ai-dev/active/I-00086/**`

Any file outside this set is a **CRITICAL** finding (scope violation).

## Test Verification (NON-NEGOTIABLE)

Run ONLY the targeted tests that exercise the modified surface area:

```bash
uv run pytest tests/dashboard/test_runtime_override_response.py -v
uv run pytest tests/ -k runtime_override -v
```

Report results. Any failure is a **CRITICAL** finding.

Do **NOT** run `make test-unit` or `make test-integration` from this step. The QV gates at S12 (`make test-unit`) and S13 (`make allure-integration`) own full-suite execution; duplicating them here blows the step's timeout budget (rule per `CLAUDE.md`, rationale: I-00073/S03 2702s timeout, 2026-05-08).

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Bug not actually fixed end-to-end; URL/id mismatch; scope violation; integration test failure; missing test named in design |
| **HIGH** | Toast message string mismatch between S01 and S05; missing acceptance-criterion coverage; missing 404 toast-absence assertion |
| **MEDIUM (fixable)** | Lint/format/typecheck violations across the change set |
| **MEDIUM (suggestion)** | Cross-cutting refactor that would improve future maintenance |
| **LOW** | Style nitpicks |

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00086",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
