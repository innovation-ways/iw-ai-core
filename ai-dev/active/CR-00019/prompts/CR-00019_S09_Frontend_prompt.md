# CR-00019_S09_Frontend_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step**: S09
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards. No docker or alembic mutation commands.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md` — read Desired Behavior (table, modal, confirm dialog, awaiting-review card) and AC1–AC14
- `dashboard/templates/pages/project/oss.html` — current OSS tab template (card layout)
- `dashboard/templates/fragments/oss_domain_card.html` — current domain-card fragment
- `dashboard/routers/oss.py` — routes that supply scan_summary + findings to the template
- `dashboard/static/styles.css` — prebuilt Tailwind
- `dashboard/templates/base.html` — layout / scripts block
- `evidences/pre/CR-00019-before-oss-tab.png` and `-expanded-card.png` — reference the current look so you understand what's being replaced

## Output Files

- Rewritten `dashboard/templates/pages/project/oss.html`
- Optionally new fragment(s) under `dashboard/templates/fragments/` (e.g. `oss_finding_row.html`, `oss_awaiting_review_card.html`, `oss_details_modal.html`) — whichever decomposition keeps the page under ~600 lines
- Delete or retire `dashboard/templates/fragments/oss_domain_card.html` (if no other caller)
- `dashboard/static/styles.css` regenerated via `make css`
- Optionally new static JS: `dashboard/static/oss_tab.js` (or inline script block in `oss.html`'s `{% block scripts %}` — match the style of the existing page, which inlines a long IIFE)
- `ai-dev/work/CR-00019/reports/CR-00019_S09_Frontend_report.md`

## Context

Replace the card layout with a selection-driven table. Add a details modal, a confirm dialog, and (when present) an awaiting-review card. Remove the top Prepare button and every dead "→ Fix via Prepare" link.

## Requirements

### 1. Remove dead/obsolete elements

- Delete the "Prepare" button at `oss.html:34-42`. Keep Scan and Publish.
- Delete the `<a href="#">→ Fix via Prepare</a>` anchors at `oss.html:305` and `oss_domain_card.html:51`.
- The existing header/banner ("HEAD has advanced since last scan" etc.) remains.
- The "CLI equivalents" details block remains (power users).

### 2. Table layout — grouped by domain

Replace the card loop (around `oss.html:240+`) with a grouped table. Each **domain** is a collapsible section (use `<details>` / `<summary>` to avoid custom JS for collapse behavior). Section header shows:

- Domain display name + description (already present in the template context).
- Per-group counts: pass / MUST / SHOULD / INFO / skip (style-matches current pills).
- A **"select all failing in this group"** checkbox that toggles every enabled row checkbox in that group (use delegated JS, not per-row onclick).

Inside each group, a `<table>` with these columns (row template should live in `fragments/oss_finding_row.html` if you decompose):

| # | Header | Content |
|---|--------|---------|
| 1 | `(checkbox)` | See rule below |
| 2 | Module | domain display name (repeated; or leave blank since grouped — your call, lean toward blank to reduce noise) |
| 3 | Title | `finding.summary` |
| 4 | Severity | pill (MUST/SHOULD/INFO/MAY) — reuse existing severity-pill classes |
| 5 | Status | pill (Pass/Fail/Skipped/Human required) — reuse existing status-pill classes |
| 6 | Details | `…` button, `data-oss-details-check="{{ finding.check_id }}"` |

Checkbox rule (reuse classes from the existing severity pills for visual consistency):

- `auto_fix_available = True` AND `status in ("fail", "human_required")` → rendered enabled, `data-check-id` and `data-check-severity` attributes set.
- `auto_fix_available = False` → rendered disabled with tooltip "Manual action — see details".
- `status == "pass"` or `status == "skip"` → no checkbox rendered.

Sort findings within each group by severity: MUST → SHOULD → INFO → MAY.

### 3. Filter chips

Above the table, render three buttons (or anchor-styled chips):

```html
<div data-oss-filter-group>
  <button data-oss-filter="all">All</button>
  <button data-oss-filter="failing" aria-pressed="true">Failing only</button>
  <button data-oss-filter="must">MUST only</button>
</div>
```

Default is "failing". On click, the JS toggles CSS classes / `hidden` attribute on rows based on data attributes (`data-row-status`, `data-row-severity`). No page reload — purely client-side.

### 4. Action row — "Prepare fix (N selected)" button

Below the filter chips, render:

```html
<button type="button"
        id="oss-prepare-fix-btn"
        disabled
        class="...">
  Prepare fix (<span data-oss-selected-count>0</span> selected)
</button>
```

JS keeps `data-oss-selected-count` in sync with checked boxes and flips `disabled` accordingly. Also disabled (with a visible "Re-scan first" tooltip/banner) when `scan_summary.is_stale` is true — pass that flag into the template context and read `data-oss-stale="true"` on a parent element.

### 5. Confirm dialog

When the user clicks the prepare button, open a modal (centered dialog, backdrop, Esc-to-close):

- Heading: "Apply N fix(es)?"
- Body: bullet list of selected check_ids with their summaries (text pulled from the already-rendered rows — no extra fetch).
- Footer: `Cancel` (close) and `Prepare fix` (submit).

On `Prepare fix`:

```javascript
fetch(`/project/${projectId}/oss/prepare`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
  body: JSON.stringify({checks: [...checkIds]}),
});
```

Response is handled by the existing stream-rendering code in the page (the POST returns `{job_id, stream_url}` as today; just adapt the existing `startOssAction` flow to use the new JSON body). The SSE feed renders unchanged.

### 6. Details modal

When the user clicks `…` in a row, open a second modal:

- Heading: `{check_id}` — `{severity}` — `{status}` pills + OSPS control code if present.
- Body sections in order:
  1. **Summary** — `finding.summary`.
  2. **Why this matters** — `finding.rationale` (fall back to `finding.detail` if empty; if both empty, omit the section).
  3. **Details** — `finding.detail` (skip if empty or identical to rationale).
  4. **Remediation** — `finding.remediation` (skip if empty).
  5. **OSPS control** — external anchor `<a href="https://baseline.openssf.org/#{{ finding.osps_control }}" target="_blank" rel="noopener">{{ finding.osps_control }} ↗</a>`. Skip if no `osps_control`.
- Closed via Esc, backdrop click, or close button.

### 7. Awaiting-review card

When any `ProjectOssJob` for this project is in `awaiting_review` (push this onto the template context from `dashboard/routers/oss.py` — likely as `awaiting_review_job: ProjectOssJob | None`), render a prominent card **above** the Scan/Publish action row:

```
┌────────────────────────────────────────────────────────────┐
│ Prepare fix pending review — job #N                        │
│ Waiting X days                                             │
│                                                            │
│ Worktree: {worktree_path}        [copy]                    │
│ Branch:   {branch_name}                                    │
│                                                            │
│ Files changed:                                             │
│   (preformatted git diff --stat output)                    │
│                                                            │
│ [Accept fix]  [Discard fix]                                │
└────────────────────────────────────────────────────────────┘
```

Accept button → POSTs `/project/{id}/oss/jobs/{job_id}/accept`, reloads the page on 200, shows the `detail` on 4xx/5xx.

Discard button → opens a small confirm dialog ("Discard the auto-fix for job #N? The worktree and branch will be deleted."), then POSTs to `/discard`.

Days-pending: compute from `job.started_at` in Jinja (`(now() - job.started_at).days`).

### 8. Remove top Prepare button logic in JS

The existing `startOssAction` handler at `oss.html:501+` currently supports `action ∈ ['scan', 'prepare', 'publish']`. Keep it for `scan` and `publish`. The selection-driven prepare uses a new path (JSON body + dedicated function), so you can either:

- Add a branch in `startOssAction` when `action === 'prepare'` to pop the confirm dialog first.
- Or keep `startOssAction` for scan/publish only and write a new `startOssPrepareSelected` for the JSON-body path.

Prefer the second — cleaner separation.

### 9. `make css`

After all template edits, run:

```bash
make css
```

This regenerates `dashboard/static/styles.css`. Commit the regenerated file. Avoid dynamic class construction (e.g. `"bg-" + color`) — Tailwind's JIT can't purge those.

### 10. Accessibility

- Checkboxes have `aria-label` describing the check they toggle.
- Modal has `role="dialog"` + `aria-modal="true"` + `aria-labelledby` pointing to the heading.
- Filter chips use `aria-pressed` for the active one.
- Keyboard support: Esc closes both modals; Tab cycles inside the open modal (focus trap if feasible — `<dialog>` element handles this natively; consider using the native `<dialog>` tag).
- Confirm dialog's primary button is focused on open.

### 11. No console errors

The page must load with zero console errors in a modern Chromium. Validate with `playwright-cli` if you want, but the QV Browser step (S19) will verify this formally.

## Project Conventions

Read `dashboard/CLAUDE.md`:

- Thin routers — if you need new server-side data (e.g. `awaiting_review_job`), add it via the existing route's context, not a new route.
- Fragment templates under `fragments/` MUST NOT extend `base.html`.
- No dynamic Tailwind class strings — keep class names literal.
- Prefer `hx-post` for forms when server-side fragment updates are simpler than JSON; but since the prepare POST carries a variable-length body, use `fetch()` with JSON (like the current page already does).
- Match the existing page's JS style (IIFE, event delegation, no framework).

## TDD Requirement

Frontend tests live mostly in S11 (integration) and S19 (browser), but for this step:

1. **RED**: Add a quick pytest-driven template-render test (`dashboard/routers/oss.py` already has a test file in `tests/integration/`). Assert:
   - The rendered HTML contains a `<button id="oss-prepare-fix-btn"` — not the old `data-oss-action="prepare"` top button.
   - No occurrence of `"→ Fix via Prepare"` in the output.
   - Finding rows have `data-check-id="..."`.
   - When a job is in awaiting_review, an element with `data-oss-awaiting-review` is rendered.
2. **GREEN**: Implement the template until these assertions pass.
3. **REFACTOR**: Decompose into fragments if the file is growing beyond ~600 lines.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — zero failures.
2. `make lint` — clean. (`make lint` includes `node --check` on JS; run that too.)
3. `make css` — runs clean and produces a diff in `dashboard/static/styles.css`.
4. Manual smoke via `playwright-cli`:
   - Open `http://localhost:9900/project/iw-ai-core/oss`.
   - `playwright-cli snapshot` — confirm table, filter chips, and Prepare button are present; no top Prepare button; no "→ Fix via Prepare" anywhere.
   - `playwright-cli kill-all` when done.
5. Your new template-render pytest passes.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "frontend-impl",
  "work_item": "CR-00019",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/pages/project/oss.html",
    "dashboard/templates/fragments/oss_finding_row.html (if new)",
    "dashboard/templates/fragments/oss_awaiting_review_card.html (if new)",
    "dashboard/templates/fragments/oss_details_modal.html (if new)",
    "dashboard/templates/fragments/oss_domain_card.html (deleted if no longer used)",
    "dashboard/static/styles.css",
    "dashboard/routers/oss.py (context additions only)",
    "tests/integration/test_cr_00019_oss_template_render.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Which fragments were decomposed; whether oss_domain_card.html was retired."
}
```
