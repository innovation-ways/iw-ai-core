# I-00040 S04 CodeReview Frontend Report

## What was done

Reviewed S03 (frontend-impl: stale-DB banner + write-action disable macro) against all 7 checklist categories.

## Findings

### 1. Banner markup correctness — PASS

- `base.html:36-53`: Banner is the **first child of `<body>`**, before the nav. ✅
- Banner is wrapped in `{% if is_db_stale(request) %}` — no markup rendered when DB is current. ✅
- `role="alert"` and `aria-live="polite"` present at `base.html:38-39`. ✅
- Banner contains `current_rev`, `head_rev`, and the literal string `make db-migrate` (line 46). ✅
- Banner contains the substring `Orch DB schema is behind head` (line 43). ✅
- No emoji. ✅
- Uses Tailwind utilities only (`bg-red-700 text-white px-4 py-3 text-sm flex items-center justify-between`) — no `style=""`. ✅

### 2. Macro correctness — PASS with one observation

- `dashboard/templates/macros/db_guard.html:1-5` defines `write_button_attrs(request)` correctly. ✅
- Macro emits `disabled aria-disabled="true" title="Orch DB schema mismatch — run 'make db-migrate' to fix."` when stale, empty string when not. ✅
- All 33 matches across 13 template files use the macro. ✅
- Read-only forms (search, filters) not modified. ✅

**Observation** — `queue.html:97-102`: The batch-create submit button has a pre-existing `disabled` attribute in the HTML (outside Jinja conditional). When `is_db_stale` is True the macro emits `disabled aria-disabled="true"` but the button already carries `disabled` from static HTML. While this is harmless (doubling `disabled` is a no-op), it means the button's disabled state is always present in the HTML source — the macro only adds the `aria-disabled` and `title`. This is a minor style inconsistency (button always shows `disabled` in markup even without the macro), not a functional defect.

### 3. Jinja global registration — PASS

- `dashboard/app.py:163-166`: `is_db_stale` registered via `templates.env.globals["is_db_stale"] = _is_db_stale`. ✅
- No template needs to import it — available everywhere. ✅

### 4. htmx interaction — PASS

- Grepped for `HX-Reswap`/`HX-Trigger` headers — none found in affected templates. ✅
- Fragment responses (daemon panel, etc.) are partial htmx swaps — they don't include `base.html` and so don't double-render the banner. ✅
- Full-page responses (all `base.html`-extending templates) include the banner. ✅

### 5. Accessibility — PASS

- `role="alert"` present. ✅
- Disabled buttons emit `disabled` (native) + `aria-disabled="true"` (macro). ✅
- Banner is non-interactive — no focus ring required. ✅

### 6. CSS regeneration — **CRITICAL ISSUE**

The S03 report states `bg-red-700` "is already in the compiled CSS" and `make css` was skipped due to corrupted `node_modules`.

However, grepping the committed `dashboard/static/styles.css` finds **no `bg-red-700` class**:

```
$ rg "bg-red-7" dashboard/static/styles.css
(no output)
```

The compiled CSS only contains `bg-red-50`, `bg-red-100`, `bg-red-500`, `bg-red-500/10`, `bg-red-500/70`, `bg-red-900`, `bg-red-950/30` — no `bg-red-700`.

The `make css` command must be run to regenerate `styles.css` so that `bg-red-700` is included, or the banner will be unstyled (invisible or default-browser-styled) in production.

**Severity: CRITICAL — functional impact: the banner will not appear with the intended red background.**

### 7. Scope drift — PASS

- No JavaScript files added or modified. ✅
- All changes are within the File Manifest scope (base.html, db_guard.html, app.py, and affected button-bearing templates). ✅

---

## Verdict

**NEEDS_FIX** — CSS regeneration is required before this can merge.

### Required fix

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040
# Fix node_modules and regenerate CSS
cd dashboard && rm -rf node_modules && npm install && npx tailwindcss -i ./input.css -o ./static/styles.css --minify
cd ..
git add dashboard/static/styles.css
git commit -m "I-00040: regenerate styles.css with bg-red-700"
```

### After fix, re-run:
- `make lint`
- `make typecheck`

Then re-trigger QV gates S08–S12 and browser verification S13.

---

## Files reviewed

| File | Lines | Notes |
|------|-------|-------|
| `dashboard/templates/base.html` | 36-53 | Banner implementation |
| `dashboard/templates/macros/db_guard.html` | 1-5 | Macro definition |
| `dashboard/app.py` | 161-166 | Jinja global registration |
| `dashboard/middlewares/alembic_guard.py` | 65-87 | `is_db_stale` and `require_db_at_head` |
| `dashboard/templates/components/action_button.html` | 1-48 | All 4 macros updated |
| `dashboard/templates/fragments/daemon_panel.html` | 81-113 | Start/stop/restart buttons |
| `dashboard/templates/pages/project/queue.html` | 97-103 | Batch-create button |
| `dashboard/templates/fragments/quality_launch.html` | 87-106 | Launch/auto-fix buttons |
| `dashboard/templates/pages/system/worktrees.html` | 15-28 | Prune button |
| `dashboard/templates/pages/system/running.html` | 129-137 | Restart-from-here button |
| `dashboard/static/styles.css` | (whole) | Checked for `bg-red-700` — NOT FOUND |