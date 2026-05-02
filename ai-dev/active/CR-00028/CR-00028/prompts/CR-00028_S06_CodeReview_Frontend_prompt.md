# CR-00028_S06_CodeReview_Frontend_prompt

**Work Item**: CR-00028 -- Don't cascade merge-time failures to dependent items
**Step Being Reviewed**: S05 (frontend-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Allowed: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00028 --json`
- `ai-dev/active/CR-00028/CR-00028_CR_Design.md`
- `ai-dev/active/CR-00028/reports/CR-00028_S05_Frontend_report.md`
- All files in S05's `files_changed`

## Output Files

- `ai-dev/active/CR-00028/reports/CR-00028_S06_CodeReview_Frontend_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in changed files = CRITICAL findings.

## Review Checklist

### 1. Visual / Status Badge

- Does `merge_failed` render with a **distinct color** from `failed`? Side-by-side, can a human tell them apart? (orange/amber vs red is the design intent.)
- Does the badge include `aria-label` for screen readers?
- Same shape, font size, padding as existing badges (no rogue styling).

### 2. Action Buttons (confirm-modal pattern)

- "Retry merge" button uses the existing `restart_merge_button` macro: `hx-get` to `/project/{project_id}/api/confirm-item/restart-merge/{item_id}`. Reused — NOT replaced with a `hx-post` + `hx-confirm` shape.
- "Abandon" button uses a NEW `abandon_merge_button` macro with the same shape: `hx-get` to `/project/{project_id}/api/confirm-item/abandon-merge/{item_id}`. Danger styling (`bg-destructive`).
- **CRITICAL — convention check**: Neither button uses `hx-confirm`. The dashboard's confirmation pattern is the modal route, not the browser-native dialog. A button with `hx-confirm` = CRITICAL finding.
- The synthetic-MERGE-step row renders BOTH buttons when `step.status == 'merge_failed'`, and only Retry when `step.status == 'failed'` (legacy back-compat).
- `_ITEM_ACTION_LABELS["abandon-merge"]` is registered with `danger=True` so the modal renders correctly.
- Button labels are clear (no jargon).

### 3. Surfaces

- Batch detail page — verified
- Item overview — verified
- Any other surface where BatchItem status is rendered — should at least show the new badge, even if the buttons aren't there

### 4. Tailwind / CSS

- If new utility classes were introduced, was `make css` run? Check `dashboard/static/styles.css` for the new classes (search for `bg-amber-` or whatever was used).
- No dynamic class construction (Tailwind JIT purging won't catch them — see `dashboard/CLAUDE.md`).

### 5. Project Conventions

- Fragment templates don't extend `base.html`
- htmx POSTs return HTML fragments (verify the action handlers in `actions.py` return fragments, not redirects)
- Jinja2 macros are reused, not copy-pasted

### 6. Accessibility

- ARIA labels on buttons
- Color is not the *only* signal (text label "Retry merge" / "Abandon" carries the meaning)
- Keyboard-navigable? Buttons are real `<button>` elements?

### 7. Browser Smoke Check

If feasible, run:

```bash
playwright-cli kill-all
playwright-cli open http://localhost:9900/project/iw-ai-core/batches
playwright-cli screenshot
```

Confirm no template rendering errors. The dev DB won't have `merge_failed` rows (migration not applied yet), so visual confirmation of the new badge is deferred to S15.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

Must pass.

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00028",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
