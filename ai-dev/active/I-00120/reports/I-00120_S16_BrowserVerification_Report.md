# Browser Verification Report — I-00120-S16

**Work Item:** I-00120 — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Step:** S16 (QV Browser)
**Agent:** qv-browser
**Date:** 2026-05-29
**Base URL:** http://localhost:9913

---

## Verifications

| ID | Name | Status | Failure Class | Screenshot |
|----|------|--------|---------------|------------|
| V0 | Pre-flight page sanity | **PASS** | — | — |
| V1 | Codex auth-state warning visible in footer | **PASS** | — | `I-00120_v1_codex_warning.png` |
| V2 | No regressions | **PASS** | — | `I-00120_v2_no_regressions.png` |

---

## V0 — Pre-flight page sanity

- `/` (projects home) — HTTP 200, no unhandled exception page ✓
- `/project/iw-ai-core/` — HTTP 200, no unhandled exception page ✓
- No `.playwright-cli/console-*.log` files found on any visited page ✓

---

## V1 — Codex auth-state warning visible in footer

**Branch observed:** `unauthenticated` (container has no `~/.local/share/opencode/auth.json`)

**Verification method:**

1. **Direct fragment fetch** (`curl -s http://localhost:9913/api/usage/llm/fragment`):
   - The Codex section contains:
     ```html
     <span class="hidden sm:flex items-center gap-1 text-amber-600"
           title="Codex not configured — run opencode auth login">
       ⚠ not configured — run opencode auth login
     </span>
     ```
   - **No** `width: 0%` bar markup is present in the Codex section ✓
   - The `text-amber-600` CSS class is present ✓
   - The `⚠` glyph is present ✓

2. **Browser snapshot** (`.playwright-cli/page-2026-05-29T12-41-44-726Z.yml`):
   - Element `e106`: `generic "Codex not configured — run opencode auth login" [ref=e106]: ⚠ not configured — run opencode auth login`
   - Confirms the warning text renders correctly in the rendered footer ✓

**Result:** PASS — the warning is correctly displayed instead of silent 0% bars.

---

## V2 — No regressions

- **Claude chip:** renders normal bars (`5h 0%`, `7d 0%`) on both the home page and project page footer ✓
- **MiniMax chip:** renders normal bar (`5h 0%`) on both pages ✓
- **Codex chip:** warning state on home page (expected — unauthenticated); no error in browser console ✓
- **Project page footer:** correct, no errors ✓
- **No console log files** created during any page visit ✓

**No regressions observed.**

---

## Console Errors Observed

None.

---

## Screenshots

| File | Description |
|------|-------------|
| `I-00120_v1_codex_warning.png` | Home page `/` — Codex footer shows `⚠ not configured — run opencode auth login` in amber, no 0% bars |
| `I-00120_v2_no_regressions.png` | Project page `/project/iw-ai-core/` — Claude and MiniMax bars render normally; no errors |

---

## Overall Result

| | |
|---|---|
| **Overall Status** | **PASS** |
| **Failure Class** | — |
| **Notes** | The `unauthenticated` branch was observed (no `auth.json` in the container). The warning `⚠ not configured — run opencode auth login` renders in `text-amber-600` in place of the two silent 0% bars, exactly as designed. The `expired` and `error` branches are covered by unit tests (`tests/unit/test_llm_usage.py`) which exercise the status discriminator logic directly. No regressions to Claude or MiniMax chips. |

---

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "I-00120",
  "overall_status": "pass",
  "overall_failure_class": null,
  "base_url_used": "http://localhost:9913",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass", "failure_class": null, "screenshot": "", "notes": "Home and project pages HTTP 200, no console errors"},
    {"id": "V1", "name": "Codex auth-state warning visible in footer", "status": "pass", "failure_class": null, "screenshot": "I-00120_v1_codex_warning.png", "notes": "unauthenticated branch observed: ⚠ not configured — run opencode auth login in text-amber-600, no 0% bars"},
    {"id": "V2", "name": "No regressions", "status": "pass", "failure_class": null, "screenshot": "I-00120_v2_no_regressions.png", "notes": "Claude and MiniMax chips render normal bars; no console errors"}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "ai-dev/active/I-00120/evidences/post/I-00120_v1_codex_warning.png",
    "ai-dev/active/I-00120/evidences/post/I-00120_v2_no_regressions.png"
  ],
  "notes": "unauthenticated branch verified. expired and error branches covered by tests/unit/test_llm_usage.py."
}
```