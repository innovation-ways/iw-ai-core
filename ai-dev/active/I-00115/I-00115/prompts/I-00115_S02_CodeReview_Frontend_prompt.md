# I-00115_S02_CodeReview_Frontend_prompt

**Work Item**: I-00115 — Amend-scope modal locks the dashboard UI after dismissal
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy — no docker mutations, testcontainer fixtures exempt. Full text: see project's `CLAUDE.md` and `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item touches NO migrations. If you see an alembic file in `files_changed`, that is itself a CRITICAL scope-creep finding.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00115 --json`
- `ai-dev/active/I-00115/I-00115_Issue_Design.md` — design document (READ FIRST)
- `ai-dev/active/I-00115/reports/I-00115_S01_Frontend_report.md` — S01 implementation report
- All files listed in S01's `files_changed` (expected: `dashboard/templates/components/scope_amend_modal.html`)
- `dashboard/routers/actions.py` (lines 215-232, 440-505) — read-only reference for the 204+toast response

## Output Files

- `ai-dev/active/I-00115/reports/I-00115_S02_CodeReview_report.md` — review report

## Context

S01 (frontend-impl) repaired the scope-amend modal's dismissal lifecycle. You are reviewing that change.

Read the design document **before** opening any file. The design names two specific defects and three additional dismissal paths (ESC + backdrop + correct submit teardown). Every one must be verified.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Both must report zero NEW violations in files S01 changed. `make lint` runs `scripts/check_templates.py` which catches `str.format`-style Jinja2 `format` filter calls — pay attention if your eye catches `{}m{}s|format(...)`. CRITICAL finding if either reports a violation in S01's `files_changed`.

## Scope Discipline

S01's `files_changed` MUST contain only `dashboard/templates/components/scope_amend_modal.html` (plus possibly a tiny CSS append to `dashboard/static/styles.css` per the project rule for broken Tailwind toolchain — that is allowed). Anything else is scope creep — CRITICAL. (Implicit allowances for `ai-dev/active/I-00115/**` still apply.)

## Review Checklist

### 1. All five dismissal paths fully tear down the modal

For each of the following, **read the actual changed template** and trace what the dismissal does:

1. **Form submit (Amend & restart) success path** — there must be cleanup wiring that fires on `htmx:afterRequest` and removes BOTH `#scope-amend-modal` AND `#scope-amend-overlay`. The cleanup MUST be inline on the `<form>` element via `hx-on::after-request="…"` (project idiom — see S01 prompt §1.1). If a script-block elsewhere in the template wires this hook instead, that is a HIGH finding — the S03 form-open-tag assertion will fail. The cleanup MUST be conditional on a successful response (2xx, e.g. `event.detail.successful`). On 4xx/5xx the modal should remain open so the operator can see the error and retry. If the cleanup fires unconditionally, that is a HIGH finding (silent error-swallowing).
2. **× close button** — the literal substring `this.closest('#scope-amend-overlay')` MUST NOT be present anywhere in the template. If it is, CRITICAL (the same bug remains).
3. **Cancel button** — removes both elements (was already correct; verify it still does).
4. **ESC key** — pressing `Escape` dismisses the modal AND the listener is detached after dismissal so it cannot leak across reopens. If the listener is attached but never removed, HIGH finding (listener leak).
5. **Backdrop click** — clicking `#scope-amend-overlay` itself dismisses; clicks inside the modal must NOT propagate to the backdrop. Verify the backdrop click handler checks `event.target === <overlay>` (or equivalent) — if every click inside the modal closes it, CRITICAL.

### 2. Server endpoint is unchanged

`dashboard/routers/actions.py` MUST NOT appear in S01's `files_changed`. If it does, CRITICAL.

### 3. Toast still shows on submit success

The page-level `htmx:afterRequest` handler at `dashboard/templates/pages/project/item_detail.html:159-172` reads `HX-Trigger: showToast`. Confirm that S01's modal-level cleanup did not stop event propagation (e.g. via `event.stopPropagation()` on `htmx:afterRequest` in a way that swallows the page-level handler). If it did, HIGH (toast silently disappears).

### 4. Accessibility regressions

- The modal's `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, and `tabindex="-1"` attributes MUST remain.
- ESC dismissal is an accessibility ADD — verify it works regardless of which element has focus inside the modal.

### 5. CLAUDE.md conventions

- No JS framework introduced.
- No `navigator.clipboard.writeText` calls (none expected for this fix).
- No hardcoded URLs / ports.
- Inline `onclick` handlers OR a single `<script>` block at the bottom of the template — either is acceptable. Multi-file JS sprawl is NOT.

### 6. Listener-leak narrative

The step report MUST explicitly explain how the ESC listener is detached. If the report doesn't say, MEDIUM (fixable) — ask S01 to clarify or to demonstrate via the code.

## Test Verification

```bash
uv run pytest tests/dashboard/ tests/integration/test_scope_amend_endpoints.py -k "scope_amend" -v
```

Existing scope-amend tests must still pass. (The new I-00115 reproduction tests are authored in S03, so they don't exist yet.)

## Severity Levels

| Severity | Action Required |
|----------|-----------------|
| CRITICAL | Must fix before merge |
| HIGH | Must fix before merge |
| MEDIUM (fixable) | Should fix in fix cycle |
| MEDIUM (suggestion) | Optional |
| LOW | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00115",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "dashboard/templates/components/scope_amend_modal.html",
      "line": 0,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
