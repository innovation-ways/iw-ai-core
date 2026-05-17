# CR-00056 S10 — Final Cross-Agent Code Review Report

**Work Item**: CR-00056 — Surface step prompts in dashboard (Prompt column + modal viewer)
**Review Step**: S10 (code-review-final-impl)
**Steps Reviewed**: S01, S02, S03, S04, S05, S06, S07, S08, S09
**Date**: 2026-05-17

---

## What Was Done

Final cross-agent review of the entire CR-00056 implementation chain (S01–S09), tracing every acceptance criterion end-to-end, verifying integration consistency, running the CLAUDE.md hard-rules sweep, and confirming that targeted tests exist and pass.

---

## Pre-Flight Gates

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ 727 files already formatted |

---

## 1. End-to-End Completeness — AC Chain Trace

| AC | Description | Integration Chain | Status |
|----|-------------|-------------------|--------|
| **AC1** | Schema additions — `prompt_text` + `fix_prompt_text` TEXT NULL on `step_runs` | S01 migration (`21de61b41cec_cr_00056_add_prompt_text_and_fix_prompt_.py`) correctly adds both columns via `op.add_column`; `make migration-check` verified in S03. Migration file is uncommitted (correct — daemon applies via merge pipeline). | ✅ PASS |
| **AC2** | Daemon snapshots initial run prompts into `StepRun.prompt_text` | `batch_manager.py` line 1531: `prompt_text=prompt_text_val` passed to `StepRun(...)` constructor; `prompt_text_val` is set from in-memory `prompt` variable (preferred) or disk fallback. IO errors swallowed with `logger.warning` — step launch proceeds regardless. | ✅ PASS |
| **AC3** | Daemon snapshots fix-cycle prompts into `fix_prompt_text` + preserves base `prompt_text` | `fix_cycle.py` lines 2370–2371: `prompt_text=base_prompt_text_val, fix_prompt_text=fix_prompt_text_val` both passed to `StepRun(...)`; `base_prompt_text_val` read from `step.prompt_file` disk path; `fix_prompt_text_val` from in-memory fix-prompt string. | ✅ PASS |
| **AC4** | Prompt column renders with View button (or `—` for synthetic/missing) | `item_steps_table.html` lines 96–109: `{% if step.is_synthetic or not step.has_prompt %}` renders `—`; otherwise renders View button. `StepDetail.has_prompt` populated via single aggregate SQL query in `_get_steps()` (items.py lines 444–469) — no N+1. | ✅ PASS |
| **AC5** | Modal opens on click, shows `<pre>` with `role="dialog" aria-modal="true"` | `get_prompt_modal` route (items.py line 1336) returns `HTMLResponse` with `prompt_text_modal.html` fragment. Fragment has `role="dialog" aria-modal="true" aria-labelledby="prompt-modal-title"`. Section body rendered in `<pre>` (line 28 of modal). | ✅ PASS |
| **AC6** | Modal dismissal: Escape, backdrop, close button — focus restored | `prompt_modal.js` implements: Escape key (line 114–118), backdrop click (line 102–104), close button (line 93–99), focus trap (lines 14–39), focus restore via `currentTrigger.focus()` (line 57–60). | ✅ PASS |
| **AC7** | Fix-cycle prompts shown in stacked sections | Route builds sections in run_number order (items.py lines 1375–1381): first run with non-null `prompt_text` → "Initial Prompt"; subsequent runs with non-null `fix_prompt_text` → "Fix Prompt (cycle N)". No upper bound on cycles — all appended. | ✅ PASS |
| **AC8** | Copy-to-clipboard via `window.iwClipboard.copy(text, button)` | `prompt_modal.js` line 69: `window.iwClipboard.copy(text, button)`. No direct `navigator.clipboard.writeText` in any S01–S09 changed file. | ✅ PASS |
| **AC9** | 404 on project/item mismatch (not 403, not 500) | Route checks `WorkItem(project_id, item_id)` → 404; checks `WorkflowStep(project_id, work_item_id=item_id, step_id=step_id)` → 404. `HTTPException(status_code=404)` used throughout (lines 1353, 1364, 1384). | ✅ PASS |

---

## 2. Cross-Agent Consistency

| Check | Status |
|-------|--------|
| Route URL `/project/{project_id}/item/{item_id}/step/{step_id}/prompt-modal` matches `hx-get` URL in template (item_steps_table.html line 104) | ✅ Exact string match |
| `StepDetail.has_prompt` (items.py line 77) used in template (item_steps_table.html line 97) | ✅ Same field |
| `data-prompt-section-body="{{ loop.index0 }}"` attribute in modal (prompt_text_modal.html line 28) read by `data-prompt-copy-section="{{ loop.index0 }}"` on copy button (line 24) via `prompt_modal.js` line 66 | ✅ Attribute name consistent |
| Agent label rendered identically in table cell (item_steps_table.html line 46) and modal header (prompt_text_modal.html line 8) | ✅ Both use `{{ step.agent_label }}` |
| CSS: `.activity-modal-*` classes reused for outer shell; `.prompt-modal-*` used only for inner section elements | ✅ No orphan CSS classes |
| Fragment `prompt_text_modal.html` does NOT extend `base.html` | ✅ Confirmed — no `{% extends %}` directive |

---

## 3. Integration Points — DB → Daemon → Route → Template

| Check | Result |
|-------|--------|
| `batch_manager.py` writes `prompt_text=prompt_text_val` at `StepRun` constructor (line 1531) | ✅ Confirmed |
| `fix_cycle.py` writes `prompt_text=base_prompt_text_val, fix_prompt_text=fix_prompt_text_val` at `StepRun` constructor (lines 2370–2371) | ✅ Confirmed |
| ORM `StepRun` has both columns (models.py lines 874, 883) | ✅ Confirmed |
| `get_prompt_modal` route reads `StepRun.prompt_text` / `.fix_prompt_text` (items.py lines 1376–1381) | ✅ Exact column names used |
| Route builds `sections` with `{"label": ..., "text": ...}` dicts — matches template `section.label` / `section.text` usage | ✅ Key names consistent |
| `has_prompt` query is a single `GROUP BY` aggregate — no N+1 | ✅ Confirmed |

---

## 4. Architecture Compliance

| Check | Result |
|-------|--------|
| `step_runs` remains append-only — no `UPDATE` statements for `prompt_text`/`fix_prompt_text` anywhere | ✅ Verified in batch_manager.py and fix_cycle.py |
| Fragment template does NOT extend `base.html` | ✅ `prompt_text_modal.html` is pure fragment |
| Section-aggregation logic in `get_prompt_modal` route is ~20 lines | ✅ Below the 40-line threshold; logic is simple and clear |

---

## 5. Security

| Check | Result |
|-------|--------|
| `{{ section.text }}` in modal rendered without `|safe` — Jinja2 autoescape in effect | ✅ Safe |
| `{{ prompt_file_display }}` in modal is unescaped text, not HTML (line 11) | ✅ Safe |
| Copy via `pre.textContent` (prompt_modal.js line 68), not `innerHTML` | ✅ Prevents XSS from copied content |
| All new routes include `project_id` in WHERE clause | ✅ AC9 compliance |
| `navigator.clipboard.writeText` only in `clipboard.js` (the approved helper) | ✅ No direct calls in changed files |

---

## 6. Performance

| Check | Result |
|-------|--------|
| `has_prompt` aggregate query runs once outside the `_get_steps()` loop | ✅ No N+1 |
| Modal lazy-loaded via htmx (not inline in table) | ✅ Keeps initial render fast for items with 25+ steps |

---

## 7. Manifest Scope Check

All files modified by S01–S09 are in `workflow-manifest.json:scope.allowed_paths`:

| File | In Manifest? |
|------|-------------|
| `orch/db/models.py` | ✅ |
| `orch/db/migrations/versions/21de61b41cec_cr_00056_add_prompt_text_and_fix_prompt_.py` | ✅ (`**` glob) |
| `orch/daemon/batch_manager.py` | ✅ |
| `orch/daemon/fix_cycle.py` | ✅ |
| `dashboard/routers/items.py` | ✅ |
| `dashboard/templates/fragments/item_steps_table.html` | ✅ |
| `dashboard/templates/fragments/prompt_text_modal.html` | ✅ |
| `dashboard/static/styles.css` | ✅ |
| `dashboard/static/prompt_modal.js` | ✅ |
| `tests/integration/test_daemon_prompt_snapshot.py` | ✅ |
| `tests/dashboard/test_prompt_modal_route.py` | ✅ |
| `dashboard/templates/base.html` (script include) | ✅ (implicit — not a code file) |

---

## 8. CLAUDE.md Hard Rules Sweep

| Pattern | Files Checked | Result |
|---------|--------------|--------|
| `navigator.clipboard.writeText` | All S01–S09 changed files | ✅ Zero hits (only in `clipboard.js` — approved helper) |
| `importlib.reload` | `test_daemon_prompt_snapshot.py`, `test_prompt_modal_route.py` | ✅ Zero hits in new test files |
| `psycopg2` (not `psycopg`) | New code in `batch_manager.py`, `fix_cycle.py`, `items.py` | ✅ Zero hits — uses `op.add_column` / SQLAlchemy only |
| `{}`.format(...) in Jinja templates | `item_steps_table.html`, `prompt_text_modal.html` | ✅ Zero hits — `make lint` via `check_templates.py` confirms `%`-style only |

---

## 9. Test Verification

Targeted tests confirmed present and passing:

**`tests/integration/test_daemon_prompt_snapshot.py`** (added by S04):
- `test_initial_run_snapshots_prompt_text` ✅ PASS
- `test_fix_cycle_snapshots_fix_prompt_text_and_base_prompt_text` ✅ PASS
- `test_fix_cycle_missing_base_prompt_file_sets_null_not_error` ✅ PASS

**`tests/dashboard/test_prompt_modal_route.py`** (added by S06, verified by S08):
- `test_returns_200_with_prompt_text` ✅ PASS
- `test_404_unknown_item` ✅ PASS
- `test_404_unknown_step` ✅ PASS
- `test_404_no_prompt_text` ✅ PASS
- `test_fix_prompt_text_sections` ✅ PASS
- `test_synthetic_step_returns_404` ✅ PASS

**Result**: 9/9 targeted tests passed in 25.13s. Coverage failure (18.86% < 50%) is pre-existing and unrelated to CR-00056.

---

## 10. S09 Findings — One Unfixed Bug

S09 (code-review-impl, frontend) raised a **HIGH** finding:

> `item_steps_table.html` line 173: Empty-state row has `colspan="9"` but the table has **11 visible columns** (Step, Agent, CLI, Model, **Prompt**, Status, Started, Duration, Runs, Error, Actions). The "No steps found." message only spans 9 columns, leaving the Prompt and Status column headers without a corresponding cell.

**Suggested fix**: Change `colspan="9"` to `colspan="11"`.

**S09 Verdict**: `NEEDS_FIX`, `mandatory_fix_count: 1`.

**This review confirms the finding is still open.** The empty-state row will render with a visual misalignment — the "No steps found." message will be narrower than the table header.

**Impact on AC4**: Does not affect AC4's View button rendering, which is the primary acceptance criterion. However, it is a layout bug that would be caught by browser E2E verification (S22).

---

## Findings Summary

| # | Severity | Step | File | Line | Description |
|---|----------|------|------|------|-------------|
| 1 | **HIGH** | S09 (open) | `dashboard/templates/fragments/item_steps_table.html` | 173 | Empty-state row `colspan="9"` should be `colspan="11"` — layout misalignment |

---

## Verdict

```
{
  "step": "S10",
  "agent": "CodeReview_Final",
  "work_item": "CR-00056",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09"],
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 1,
  "findings": [
    {
      "severity": "HIGH",
      "file": "dashboard/templates/fragments/item_steps_table.html",
      "line": 173,
      "description": "Empty-state row has colspan=\"9\" but table has 11 columns. Change to colspan=\"11\".",
      "step_where_found": "S09"
    }
  ],
  "tests_passed": true,
  "test_summary": "9 passed (3 integration + 6 dashboard), 0 failed. Coverage failure is pre-existing.",
  "missing_requirements": [],
  "notes": "AC1–AC9 all trace correctly through the implementation chain. The S09 HIGH finding (colspan mismatch in empty-state row) must be fixed before S11 (tests-impl) to avoid tests passing on a broken layout. All other aspects are clean: no UPDATE on step_runs, no psycopg2 imports, no navigator.clipboard.writeText calls in changed files, fragment does not extend base.html, Jinja format uses %-style, has_prompt query has no N+1, 404 semantics are correct."
}
```

**Recommendation**: Fix the `colspan="11"` issue in `item_steps_table.html` before proceeding to S11 (tests-impl), to ensure the TDD approach starts from a correct template. The fix is a one-line change.
