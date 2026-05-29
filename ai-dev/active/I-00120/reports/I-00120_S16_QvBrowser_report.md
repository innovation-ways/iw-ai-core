# I-00120 S16 — Browser Verification (qv-browser)

## What was done

Verified that the Codex usage chip in the dashboard footer renders a warning (`⚠ not configured — run opencode auth login` in amber) instead of silent 0% bars when no opencode OAuth token is present.

## Files examined

- `orch/llm_usage.py` — confirmed `_codex_usage()` returns `status: "unauthenticated"` when `auth.json` is missing
- `dashboard/routers/usage.py` — confirmed `_CODEX_WARNING_MAP` maps `unauthenticated` → warning text, passed to template as `codex_warning`
- `dashboard/templates/fragments/llm_usage_footer.html` — confirmed `{% if codex_warning %}` branch renders warning in `text-amber-600` instead of bars

## Verifications

| ID | Name | Result |
|----|------|--------|
| V0 | Pre-flight page sanity | PASS |
| V1 | Codex warning visible in footer | PASS |
| V2 | No regressions | PASS |

## Branch observed

`unauthenticated` — the E2E app container has no `~/.local/share/opencode/auth.json`, so `_codex_usage()` returns `status: "unauthenticated"`, the router maps it to `not configured — run opencode auth login`, and the fragment renders the warning with `⚠` glyph and `text-amber-600` class. No 0% bars appear for this state.

## Screenshots

- `evidences/post/I-00120_v1_codex_warning.png` — home page footer showing the warning
- `evidences/post/I-00120_v2_no_regressions.png` — project page showing Claude/MiniMax bars normal

## Result

**PASS** — all verifications passed. The fix is confirmed working in the browser.