# I-00120_S04_CodeReview_prompt

**Work Item**: I-00120 — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Do not run any command that changes Docker state. Read-only introspection, testcontainer fixtures, and
`./ai-core.sh` / `make` targets are allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item.

## Input Files

- Runtime step state: `uv run iw item-status I-00120 --json`.
- `ai-dev/active/I-00120/I-00120_Issue_Design.md` — design document.
- `ai-dev/work/I-00120/reports/I-00120_S03_Frontend_report.md` — implementation report.
- Files in S03's `files_changed` (`dashboard/routers/usage.py`, `dashboard/templates/fragments/llm_usage_footer.html`).

## Output Files

- `ai-dev/work/I-00120/reports/I-00120_S04_CodeReview_report.md` — review report.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint     # includes scripts/check_templates.py for the Jinja2 fragment
make format
```
New violations in changed files → CRITICAL (`category: conventions`).

## Review Checklist (item-specific)

1. **Status → message mapping** matches the design doc's **Warning message mapping** table exactly
   (`expired` → "token expired — re-authenticate", `unauthenticated` → "not configured — run opencode
   auth login", `error` → "usage unavailable", `ok` → no warning).
2. **Conditional render** — the fragment shows the warning **in place of** the two bars when
   `codex_warning` is set, and shows the normal bars when status == `ok`. Both branches are reachable
   and well-formed HTML.
3. **CSS class is pre-compiled** — the warning uses `text-amber-600` (already in
   `dashboard/static/styles.css`); no brand-new uncompiled Tailwind class was introduced, and no
   `make css` dependency was added (CLAUDE.md / I-00067). Verify: `grep -c "text-amber-600" dashboard/static/styles.css` > 0.
4. **Thin router** — the router only does the trivial status→message mapping; no business logic leaked
   in. Claude/MiniMax context is unchanged. The stale-cache fallback dict carries `status: error`.
5. **`format` filter style** — any `|format(...)` use is `%`-style, not `str.format`-style (CLAUDE.md).
6. **No collateral changes** — Claude/MiniMax fragment sections untouched; fragment still does not
   extend `base.html`.

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW. `verdict: pass` only when zero
CRITICAL + HIGH + MEDIUM_FIXABLE.

## Test Verification

Render the fragment route (or run the dashboard test file if present) to confirm both branches render.
Do not run the full suite. Report results accurately.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00120",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
