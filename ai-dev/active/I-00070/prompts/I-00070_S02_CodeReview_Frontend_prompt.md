# I-00070_S02_CodeReview_Frontend_prompt

**Work Item**: I-00070 -- Copy paste prompt button silently fails over plain HTTP from a non-localhost hostname
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Standard policy. No container operations are required for this step. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch Alembic migrations.

## Input Files

- `ai-dev/active/I-00070/I-00070_Issue_Design.md` — Design document
- `ai-dev/active/I-00070/reports/I-00070_S01_Frontend_report.md` — S01 report
- `dashboard/static/clipboard.js` — new helper to review
- `dashboard/templates/base.html` — script tag wiring
- `dashboard/templates/fragments/item_execution_report.html`, `.../oss_cli_block.html`, `.../oss_install_modal.html`, `dashboard/templates/pages/project/oss.html`, `dashboard/static/chat/actions.js`, `dashboard/static/chat/render.js` — migrated callsites
- `dashboard/CLAUDE.md` — updated convention note

## Output Files

- `ai-dev/active/I-00070/reports/I-00070_S02_CodeReview_Frontend_report.md` — review findings + verdict

## Review Checklist (every item is a hard-fail if not met)

1. **Helper correctness — secure-context branch**: when `window.isSecureContext === true` AND `navigator.clipboard.writeText` is a function, the helper calls `navigator.clipboard.writeText(text)` and returns its promise. No textarea is created in this branch.
2. **Helper correctness — fallback branch**: when either condition is false, the helper creates a fixed-position off-screen `<textarea>`, selects it, calls `document.execCommand('copy')`, and removes the textarea in a `finally` block. Resolves the promise on `true`, rejects on `false` or thrown exception.
3. **Failure surfaces**: the helper REJECTS on failure. It does NOT swallow errors with `catch(_) {}`. The rejection still triggers the "Copy failed" UI label.
4. **UI feedback**: button label changes to "Copied" (success) or "Copy failed" (failure) for ~1500 ms then restores. The original label is cached in `button.dataset.iwClipboardOriginal` so repeated rapid clicks restore consistently. When `button` is `null`/`undefined`, the helper does NOT throw and skips the UI step.
5. **No global pollution**: the file is wrapped in an IIFE; only `window.iwClipboard` is exposed.
6. **Every callsite migrated**: after S01, `grep -rn "navigator.clipboard.writeText" dashboard/` MUST list ONLY `dashboard/static/clipboard.js`. Run this grep yourself and paste the output in your report.
7. **OSS page local helper removed**: `dashboard/templates/pages/project/oss.html` MUST NOT define its own `copyToClipboard`. The OSS page's checkmark `'✓'` logic either is removed (preferred) OR runs only after the helper's promise resolves — never both.
8. **base.html load order**: `<script src="/static/clipboard.js"></script>` is placed BEFORE any inline `<script>` blocks that call `iwClipboard.copy(...)` execute. It is loaded synchronously (no `defer`).
9. **Escape safety**: any callsite that interpolates a Jinja2 expression into an inline `onclick` (e.g. `'{{ info.install_cmd }}'` in oss_install_modal.html) is escaped by the default Jinja2 autoescape. Verify the rendered HTML escapes single quotes / angle brackets correctly. If the source is not safe-escaped, the bug is potentially worse than the original.
10. **No leaked textareas**: search for `removeChild` in the helper — it MUST be in `finally` so an exception in `execCommand` still removes the textarea.
11. **Accessibility**: the button text change is sufficient feedback for screen readers when the button has visible focus. Confirm `aria-live="polite"` is NOT needed (the button itself updates and is the focus target). Note in the review.
12. **CLAUDE.md updated**: `dashboard/CLAUDE.md` contains the new "Clipboard buttons" subsection.
13. **Pre-flight gates passed**: S01's report shows `format`, `typecheck`, `lint` all `ok` (or `fixed` for format). If any are `skipped`, this is a hard-fail.

## Findings & Verdict

Produce a markdown report listing each checklist item with a CHECK / ISSUE / N/A status and a 1-line justification.

End with:

```
Verdict: PASS | FIX_REQUIRED
```

If `FIX_REQUIRED`, list the specific changes the implementer must make. Be precise (file:line).

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00070",
  "review_target_step": "S01",
  "verdict": "pass|fix_required",
  "findings": [
    {"severity": "high|med|low", "file": "path:line", "issue": "...", "fix": "..."}
  ],
  "notes": ""
}
```
