# CR-00019_S10_CodeReview_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step Being Reviewed**: S09 (frontend-impl — table, modal, confirm dialog, awaiting-review card)
**Review Step**: S10

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md`
- `ai-dev/work/CR-00019/reports/CR-00019_S09_Frontend_report.md`
- All files listed in S09's `files_changed`

## Output Files

- `ai-dev/work/CR-00019/reports/CR-00019_S10_CodeReview_report.md`

## Context

You are reviewing S09: the OSS tab UI rewrite.

## Review Checklist

### 1. Dead elements removed

- Confirm **no** `→ Fix via Prepare` anchors remain in any template. Grep:
  ```
  grep -r "Fix via Prepare" dashboard/templates/
  ```
  Expected result: empty.
- Confirm **no** top Prepare button: grep for `data-oss-action="prepare"`. Expected: empty.
- `oss_domain_card.html` either deleted or no longer rendered (if still present, flag why).

### 2. Table structure

- Grouped by domain with collapsible sections (using `<details>`/`<summary>` or a deterministic JS toggle).
- Per-row columns: checkbox, module, title, severity, status, details `…` button.
- Rows sorted within each group: MUST → SHOULD → INFO → MAY.

### 3. Checkbox rule

- `auto_fix_available=true` → enabled checkbox present, has `data-check-id` attribute.
- `auto_fix_available=false` + `status in (fail, human_required)` → checkbox present but disabled, with tooltip.
- `status in (pass, skip)` → no checkbox.

### 4. Filter chips

- Three chips: All, Failing only, MUST only. Default = Failing only.
- Filter is client-side (CSS class toggle or `hidden` attribute) — no server round-trip.
- `aria-pressed` reflects the active chip.

### 5. Modal + confirm dialog

- Details modal renders summary, rationale (fallback to detail), detail, remediation, OSPS link in that order. Sections absent when empty.
- OSPS link is `https://baseline.openssf.org/#{{ osps_control }}` with `target="_blank"` and `rel="noopener"`.
- Confirm dialog lists **every** selected check_id with its summary.
- Both modals close on Esc and backdrop click.
- Both have `role="dialog"` + `aria-modal="true"` + `aria-labelledby`.

### 6. Awaiting-review card

- Renders only when `awaiting_review_job` is non-null in the context.
- Shows worktree path, branch, files-changed summary (preformatted), days-pending age.
- Accept button POSTs `/jobs/{id}/accept` and handles 200 / 409 / 500.
- Discard button opens a confirm before POSTing `/discard`.

### 7. Stale scan

- When `scan_summary.is_stale` is true, the Prepare button is disabled **even when** selection ≥ 1, with a visible "Re-scan first" hint.

### 8. Tailwind / CSS

- No dynamic class strings (`"bg-" + x`). Flag any that exist.
- `make css` was run and the diff is included in the commit.
- No regressions on existing pills (severity, status).

### 9. Accessibility

- Keyboard: Esc closes modals; Tab cycles inside; confirm's primary button receives focus on open.
- aria-label on checkboxes describes the check they toggle.
- Color isn't the only indicator of state (icons / text present on pills).

### 10. JS hygiene

- No new console errors on page load.
- Event delegation (one listener at a common ancestor), not per-row onclick.
- No framework introduced.
- No inline `onclick="..."` attributes in generated HTML.

### 11. No regressions

- Scan button still works.
- Publish button still works.
- SSE streaming still wires up on fire-and-poll.
- Existing stale banner remains.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — zero failures.
2. `make lint` — clean (ruff + `node --check`).
3. Re-run S09's template-render tests — pass.
4. Spot-check via `playwright-cli` against `http://localhost:9900/project/iw-ai-core/oss`:
   - `playwright-cli kill-all; playwright-cli open <url>; playwright-cli snapshot`
   - Confirm the expected structure.
   - Click a `…` button; confirm modal opens with rationale + OSPS link.
   - `playwright-cli kill-all` when done.

## Severity Levels

Standard. Dynamic Tailwind class → HIGH. Modal not closeable on Esc → HIGH. Checkbox rule wrong → HIGH. Dead "Fix via Prepare" still present → CRITICAL (regression of primary AC1). Top Prepare button still present → CRITICAL.

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "CodeReview",
  "work_item": "CR-00019",
  "step_reviewed": "S09",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
