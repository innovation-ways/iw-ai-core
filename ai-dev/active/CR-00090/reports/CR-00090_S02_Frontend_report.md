# CR-00090 S02 Frontend — Step Report

**Work Item**: CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var  
**Step**: S02  
**Agent**: frontend-impl  
**Status**: ✅ complete

---

## What Was Done

Updated three Jinja2 templates that used UA-sniffing for `_headless` detection to include `_e2e_mode` as the primary driver, and added `IW_CORE_E2E_MODE: "true"` to the worktree compose template so all E2E containers suppress polling unconditionally.

### Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/base.html` | Replaced `{% set _headless = ('headlesschrome' in _ua) or ('playwright' in _ua) %}` → `{% set _headless = _e2e_mode or ('headlesschrome' in _ua) or ('playwright' in _ua) %}` (sidebar worktree badge) |
| `dashboard/templates/fragments/staleness_dot.html` | Removed `|_default(false)` from `_e2e_mode`; expression now `{% set _headless = _e2e_mode or ... %}` |
| `dashboard/templates/pages/project_selector.html` | Same simplification; removed `|_default(false)` from `_e2e_mode` |
| `ai-dev/iw-config/worktree-compose.template.yml` | Added `IW_CORE_E2E_MODE: "true"` to the `app` service's `environment:` block |

### Notes

- `staleness_dot.html` and `project_selector.html` already had `|_default(false)` on `_e2e_mode` — consistent with the intent but redundant since S01 guarantees `_e2e_mode` is always in the template context. Simplified these to match `base.html`.
- The `_headless` variable name is preserved everywhere; downstream `hx-get`/`hx-trigger` usage is unchanged.
- `_e2e_mode` comes from S01 (`dashboard/app.py` injects it as a Jinja global), so no per-route changes were needed.

---

## Preflight Quality Gates

| Check | Result |
|-------|--------|
| `make format` | ok — 943 files already formatted |
| `make lint` | ok — all checks passed including `scripts/check_templates.py` |
| `make typecheck` | ok — 0 errors in 281 source files |

---

## Test Results

```
uv run pytest tests/unit/ -v -q --no-cov
3626 passed, 7 skipped, 5 xfailed, 3 xpassed in 61.04s
```

No regressions introduced by this step.

---

## TDD Red Evidence

n/a — template and compose YAML edits only; no production Python logic changed.
