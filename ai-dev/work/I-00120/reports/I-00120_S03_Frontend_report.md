# I-00120 S03 — Frontend Implementation Report

**Step**: S03
**Agent**: frontend-impl
**Work Item**: I-00120 — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Completion**: ✅ complete

---

## What Was Done

Implemented the frontend half of the fix: mapped the backend `status` discriminator to
visible warning text and replaced the silent zeroed bars with an amber inline warning.

### `dashboard/routers/usage.py`

- Added a module-level `_CODEX_WARNING_MAP` dict mapping each non-ok status to the
  user-facing warning string (per the design doc's **Warning message mapping** table).
- In `llm_usage_fragment()`:
  - Read `codex_status = codex.get("status") or "ok"` from the backend dict.
  - Looked up `codex_warning = _CODEX_WARNING_MAP.get(codex_status)` — `None` when status is `"ok"`.
  - Passed both `codex_warning` and `codex_status` to the template context.
  - Updated the stale-cache fallback dict to include `"status": "error"` so a
    pre-upgrade in-process cache surfaces `"usage unavailable"` instead of silent 0% bars.

### `dashboard/templates/fragments/llm_usage_footer.html`

- Wrapped the Codex bars in a `{% if codex_warning %}…{% else %}…{% endif %}` Jinja2 block.
- When `codex_warning` is falsy (`status == "ok"`): bars render unchanged.
- When `codex_warning` is set: renders a single inline `<span>` replacing both bars:

  ```html
  <span class="hidden sm:flex items-center gap-1 text-amber-600"
        title="Codex {{ codex_warning }}">⚠ {{ codex_warning }}</span>
  ```

- `text-amber-600` is an already-compiled Tailwind class in `dashboard/static/styles.css` —
  no `make css` run required (I-00067 / CLAUDE.md).
- The `Codex` label line and its `title="ChatGPT {{ codex_plan_type }} plan"` behaviour are unchanged.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/usage.py` | Added `_CODEX_WARNING_MAP`; read `codex_status`; built `codex_warning`; passed both to template context; updated stale-cache fallback dict |
| `dashboard/templates/fragments/llm_usage_footer.html` | `{% if codex_warning %}` branch replaces bars with amber warning span |

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ 973 files already formatted |
| `make typecheck` | ✅ no issues found (287 source files) |
| `make lint` (incl. `check_templates.py`) | ✅ All checks passed |

## Test Verification (Targeted — not full suite)

Used `TestClient` with `get_llm_usage` patched to exercise all four statuses and the stale-cache
fallback path:

| Check | Result |
|-------|--------|
| `ok`: two Codex bars present | ✅ |
| `ok`: no amber-600 class | ✅ |
| `ok`: no ⚠ glyph | ✅ |
| `expired`: amber-600 class present | ✅ |
| `expired`: ⚠ glyph present | ✅ |
| `expired`: "token expired" message in output | ✅ |
| `expired`: zero bars (warning replaces them) | ✅ |
| `unauthenticated`: amber-600 class present | ✅ |
| `unauthenticated`: "not configured" message | ✅ |
| `error`: amber-600 class present | ✅ |
| `error`: "usage unavailable" message | ✅ |
| fallback (pre-upgrade cache, no `codex` key): amber-600 shown | ✅ |

**All 13 checks passed.** Full-suite gate is owned by S05 (`tests-impl`).

## Blockers

None.

## Notes

- The `⚠` glyph and `text-amber-600` class live entirely in the template (presentation layer),
  keeping the router thin as per conventions.
- The `IW_CORE_OPERATOR_APPLY=true` env var was required to bypass `LiveDbConnectionRefusedError`
  during the targeted render test (the dashboard app tries to resolve DB identity at startup;
  `create_app()` in `app.py` calls `verify_instance_identity()` even when `get_db` is overridden).
  This is not a code issue — it's specific to this in-process test invocation.
