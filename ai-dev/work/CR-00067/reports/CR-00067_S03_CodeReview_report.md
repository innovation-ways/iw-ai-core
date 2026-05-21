# CR-00067 S03 Code Review Report

**Work Item**: CR-00067 — AI Assistant Context Usage Percentage Indicator
**Review Step**: S03 (Code Review)
**Reviewed Steps**: S01 (Backend), S02 (Frontend)
**Agent**: code-review-impl

---

## Quality Gates

| Check | Result |
|-------|--------|
| `make lint` | ✅ PASSED |
| `make format-check` | ✅ PASSED (821 files already formatted) |
| `uv run pytest tests/unit/test_context_usage.py` | ✅ 32 passed |
| `uv run pytest tests/dashboard/test_chat_context_pct_template.py` | ✅ 11 passed |
| `uv run pytest tests/integration/test_chat_tabs_api.py -k context` | ✅ 3 passed |

---

## Review Checklist

### 1. Backend — `orch/chat/context_usage.py` ✅ PASS

| Requirement | Finding |
|-------------|---------|
| Pure module (no DB/HTTP/I/O) | ✅ Correctly pure. |
| Token summing defaults all sub-fields to 0 | ✅ `_int()` helper handles `None`, missing keys, and non-numeric types. |
| "No data" path returns `None` | ✅ Empty messages, `None` context window, zero/negative window, zero used-tokens all return `None`. |
| Percentage clamped to `[0, 100]` | ✅ Explicit clamp. |
| Most-recent assistant selected | ✅ `reversed(messages)` scan. |
| `info.role` fallback for OpenCode payloads | ✅ Both `role` and `info_role` handled with priority logic. |

### 2. Backend — `dashboard/routers/chat.py` (`get_tab`) ✅ PASS

| Requirement | Finding |
|-------------|---------|
| `context_pct` injected only when session is a dict and value is numeric | ✅ Lines 765–775. |
| `{tab, session, messages}` return shape preserved | ✅ Only additive injection. |
| `/config/providers` cached (30 s TTL, not on every call) | ✅ `_get_providers_cached()` with `_PROVIDERS_TTL = 30.0` and `_providers_cache` dict — same pattern as existing `_config_cache`. |
| Failures swallowed (never returns error) | ✅ Wrapped in `contextlib.suppress(Exception)`. |
| Router stays thin (arithmetic in helper) | ✅ `context_usage.compute_context_pct()`, no inline arithmetic. |

### 3. Frontend — `composer.html` ✅ PASS

| Requirement | Finding |
|-------------|---------|
| `<span id="chat-assistant-context-pct">` present | ✅ |
| Positioned before `#chat-assistant-clear` | ✅ Element is the first child of the `<div class="flex items-center gap-2">` flex row. |
| `hidden` class by default | ✅ `class="chat-assistant-context-pct hidden"`. |
| `aria-label` and `title` present | ✅ `aria-label="Context window used" title="Context window used"`. |
| No other composer control modified | ✅ Only the new `<span>` was added. |

### 4. Frontend — `chat.css` ✅ PASS

| Requirement | Finding |
|-------------|---------|
| Rules appended to `chat.css` (not new file, not `styles.css`) | ✅ Appended to `dashboard/static/chat_assistant/chat.css`. |
| `.chat-assistant-context-pct` base rule with neutral muted colour | ✅ `color: var(--muted-foreground)`. |
| `.is-warn` (amber) modifier rule | ✅ `color: #92400e` with dark-mode override `color: #fcd34d`. |
| `.is-crit` (destructive) modifier rule | ✅ `color: var(--destructive)`. |
| `hidden` utility not redefined | ✅ No redefinition of `.hidden`. |

### 5. Frontend — `chat.js` ✅ PASS

| Requirement | Finding |
|-------------|---------|
| Single shared helper `_refreshContextPct` | ✅ `setInterval` now calls `_refreshContextPct(tabId)` — fetch not duplicated. |
| Percentage `Math.round`-ed (no fractional `%`) | ✅ `Math.round(pct)` before concatenation. |
| Missing/`null`/`NaN` `context_pct` → hidden with empty `textContent` | ✅ `_applyContextPct(NaN)` hides and clears. |
| Colour bands: `>=90` → `is-crit`; `>=70 && <90` → `is-warn`; `<70` → neither | ✅ `isFinite` check first, then band checks. Stale band classes removed first. |
| Immediate fetch on tab activation inside `_activateTab()` | ✅ `_refreshContextPct(tabId)` called after `_updateClearButton()`. |
| No active tab → element hidden with empty text | ✅ `_refreshContextPct(null)` called in `_closeTab` when `_tabs.length === 0`. |
| `title` and `aria-label` updated with live percentage | ✅ `'Context window used: ' + rounded + '%'` applied to both. |
| Fetch errors swallowed silently | ✅ `.catch(function () { /* ignore */ })` matches existing convention. |

### 6. Tests ✅ PASS

| Test file | Finding |
|----------|---------|
| `tests/unit/test_context_usage.py` (32 tests) | RED evidence recorded (`ImportError: cannot import name 'compute_context_pct'`). All 32 tests now GREEN and cover: token summing with missing fields, clamping, every `None` path, most-recent assistant selection, `info.role` fallback, `lookup_context_window`, `resolve_model_from_tab`. |
| `tests/integration/test_chat_tabs_api.py` (3 new tests) | `test_get_tab_injects_context_pct_when_token_data_present`, `test_get_tab_omits_context_pct_when_no_token_data`, `test_get_tab_omits_context_pct_when_context_window_unknown` — all pass. |
| `tests/dashboard/test_chat_context_pct_template.py` (11 tests) | `TestComposerDom` (3): element exists, starts `hidden`, precedes `#chat-assistant-clear`. `TestContextPctCss` (3): base rule, `is-warn`, `is-crit`. `TestContextPctJsHelpers` (5): `_applyContextPct`, `_refreshContextPct`, NaN-hide on falsy tabId, immediate fetch in `_activateTab`, poll delegates to `_refreshContextPct`. |

### 7. Scope Check ✅ PASS

Changed files are a subset of the design's **Impacted Paths**:

| File | In Impacted Paths? | Status |
|------|------------------|--------|
| `orch/chat/context_usage.py` | ✅ | Expected |
| `dashboard/routers/chat.py` | ✅ | Expected |
| `dashboard/templates/chat_assistant/composer.html` | ✅ | Expected |
| `dashboard/static/chat_assistant/chat.css` | ✅ | Expected |
| `dashboard/static/chat_assistant/chat.js` | ✅ | Expected |
| `tests/integration/_fake_opencode.py` | ✅ | Expected (test support file) |
| `tests/integration/test_chat_tabs_api.py` | ✅ | Expected |
| `tests/unit/test_context_usage.py` | ✅ | Expected |
| `tests/dashboard/test_chat_context_pct_template.py` | ✅ | Expected |

Two additional files appeared as modified in git status but are **not** in the Impacted Paths:

| File | Change | Assessment |
|------|--------|------------|
| `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py` | Whitespace-only reformatting of a comment. | MEDIUM_SUGGESTION — unintentional change. |
| `tests/integration/test_dashboard_remaining.py` | Addition of a blank line before an `import re` statement. | MEDIUM_SUGGESTION — unintentional change. |

Both changes are whitespace-only (no functional impact) and do not cause lint violations. Flagged as suggestions to revert if a future agent wants a strictly scoped diff.

---

## Findings Summary

| # | Severity | Area | Finding |
|---|----------|------|---------|
| 1 | MEDIUM_SUGGESTION | Tests | `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py` has a whitespace-only change (comment reformatting) unrelated to CR-00067. Revert recommended. |
| 2 | MEDIUM_SUGGESTION | Tests | `tests/integration/test_dashboard_remaining.py` has a blank-line insertion unrelated to CR-00067. Revert recommended. |

**Mandatory fix count**: 0
**Tests passed**: true
**Verdict**: pass

---

## Notes

- The `_providers_cache` design mirrors the existing `_config_cache` pattern exactly — both use a `{"data": ..., "at": ...}` slot with TTL.
- `context_pct` is correctly omitted for Pi tabs (graceful degradation — frontend label stays hidden). This matches the design's documented Pi limitation.
- The RED phase is correctly recorded in `tests/unit/test_context_usage.py` at the bottom of the file (module did not exist when the file was first created).
- No migrations were added — this CR required none.
- No Docker usage outside testcontainers — policy compliant.