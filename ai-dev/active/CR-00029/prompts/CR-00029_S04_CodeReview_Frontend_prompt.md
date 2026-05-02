# CR-00029_S04_CodeReview_Frontend_prompt

**Work Item**: CR-00029 -- Add Restart button to the synthetic Worktree Setup (S00) row
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Allowed: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00029 --json`
- `ai-dev/active/CR-00029/CR-00029_CR_Design.md`
- `ai-dev/active/CR-00029/reports/CR-00029_S03_Frontend_report.md`
- All files in S03's `files_changed`

## Output Files

- `ai-dev/active/CR-00029/reports/CR-00029_S04_CodeReview_Frontend_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in changed files = CRITICAL findings (`category: conventions`).

## Review Checklist

### 1. Macro definition

- `restart_setup_button(project_id, item_id)` is structurally identical to `restart_merge_button`.
- Uses the same `bg-secondary text-secondary-foreground` classes (no new Tailwind utilities introduced).
- `title` attribute present for tooltip / accessibility.
- `write_button_attrs(request)` macro applied (DB-guard pattern).
- `hx-get` URL matches the actual backend route from S01. **CRITICAL** if the URL prefix is wrong — clicking the button would 404.

### 2. `item_overview.html` change

- The new conditional branch is ABOVE `{% elif not step.is_synthetic %}` so the synthetic-S00-restartable case is matched first.
- The check is precise: `step.is_synthetic and step.step_id == 'S00' and step.restartable`.
- The macro is imported at the top of the template (not redundantly anywhere else).
- No accidental indentation/whitespace changes that would affect the existing branches.

### 3. No regression matrix

Verify each existing case still renders the right button (no button silently disappeared):

| Case | Expected | Verified? |
|------|----------|-----------|
| MERGE row, status=failed | `restart_merge_button` | □ |
| MERGE row, other status | no button | □ |
| Synthetic S00, restartable=True | `restart_setup_button` (NEW) | □ |
| Synthetic S00, restartable=False | no button | □ |
| Other synthetic rows | no button | □ |
| Non-synthetic, status=failed/needs_fix | `restart_button` + `skip_button` | □ |
| Non-synthetic, status=in_progress | `kill_button` | □ |
| Non-synthetic, other status | no button | □ |

Walk the diff and check each branch — even a small reorder can break this.

### 4. Accessibility

- Button has a meaningful `title` attribute.
- Text label "↻ Restart Setup" is readable (the `↻` is decorative; the text carries the meaning).
- Color is not the only signal.
- Real `<button>` element (not a `<div>` with `onclick`).

### 5. Confirm-dialog flow

- Manually trace: user clicks button → `hx-get` to confirm endpoint → dialog appears → user clicks confirm → POST to action endpoint → response reloads the item-overview fragment. Verify the `hx-target` and `hx-swap` make this work.

### 6. Smoke render

Skip the live-dashboard smoke check at this stage — it requires a real setup-failed item which we cannot guarantee is present. Visual verification is deferred to S13 (browser verification), which seeds its own fixture. For S04, rely on reading the diff and confirming the conditional, the macro shape, and the unit tests cover the rendering logic.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00029",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
