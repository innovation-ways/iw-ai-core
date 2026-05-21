# CR-00067 S05 Code Review Final Report

**Work Item**: CR-00067 — AI Assistant Context Usage Percentage Indicator
**Step**: S05 (Code Review Final)
**Agent**: code-review-final-impl

---

## Pre-Review Gate

| Check | Result |
|-------|--------|
| `make lint` (ruff check) | ✅ PASSED |
| `make format-check` | ⚠️ 2 pre-existing whitespace-only reformat suggestions in unrelated files (see §Scope) |

---

## Cross-Step Review

This review validates that S01 (backend) + S02 (frontend) + S04 (fixes) together
produce a correct, complete, end-to-end feature. All checks below are verified
against the actual files on disk in the CR-00067 worktree.

---

### 1. Acceptance Criteria — All AC1–AC6 Satisfied

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC1 | Backend computes and returns `context_pct` as `round(used_tokens / context_window * 100)` clamped [0, 100] | ✅ | `orch/chat/context_usage.py:compute_context_pct` sums all 5 token sub-fields, divides by `context_window`, clamps explicitly |
| AC2 | `context_pct` omitted when usage cannot be computed | ✅ | `compute_context_pct` returns `None` for: no assistant message, no tokens, `context_window` ≤ 0, `used_tokens` ≤ 0. `get_tab` only injects into session when `pct is not None` |
| AC3 | Context % label visible left of Clear button | ✅ | `composer.html` line 32: `<span id="chat-assistant-context-pct">` is the first child of the flex row containing Clear |
| AC4 | Label hidden when no context data | ✅ | `chat.js:_applyContextPct` sets `el.classList.add('hidden')` and `textContent=''` for non-finite `pct`; `_refreshContextPct(null)` called in `_closeTab` when no tabs remain |
| AC5 | Colour bands <70% neutral, ≥70%<90% amber, ≥90% red | ✅ | `chat.js:_applyContextPct` checks `>=90 → is-crit`, `>=70 → is-warn`; CSS rules in `chat.css` define `color: var(--muted-foreground)` (base), `color: #92400e` (is-warn), `color: var(--destructive)` (is-crit); dark-mode override `color: #fcd34d` for is-warn |
| AC6 | Fetch on tab activation | ✅ | `chat.js:_activateTab` calls `_refreshContextPct(tabId)` at the end |

---

### 2. End-to-End Contract — No Name or Nesting Mismatch

| Location | Field path | Verified |
|----------|-----------|---------|
| Backend injects (`chat.py:774`) | `session["context_pct"] = pct` | ✅ |
| Frontend reads (`chat.js:1936`) | `session && session.context_pct` | ✅ |
| Template renders (`composer.html:32`) | `id="chat-assistant-context-pct"` | ✅ |

Exact match on field name (`context_pct`), nesting level (inside `session` object),
and DOM id — no typos, no case differences.

---

### 3. Integration — DOM Id Consistency

- `composer.html` line 32: `id="chat-assistant-context-pct"`
- `chat.js:1920`: `document.getElementById('chat-assistant-context-pct')`
- `chat.js:1933`: `document.getElementById('chat-assistant-context-pct')`

✅ Id is unique in the document (prefixed `chat-assistant-` per convention).

---

### 4. CSS Classes — All Selectors Match Exactly

| Class applied in JS | Selector in `chat.css` | Match |
|--------------------|-----------------------|-------|
| `hidden` | `.hidden` (global Tailwind utility — no redefinition in chat.css) | ✅ |
| `chat-assistant-context-pct` (base) | `.chat-assistant-context-pct { color: var(--muted-foreground); ... }` | ✅ |
| `is-warn` | `.chat-assistant-context-pct.is-warn { color: #92400e; }` + dark-mode | ✅ |
| `is-crit` | `.chat-assistant-context-pct.is-crit { color: var(--destructive); }` | ✅ |

No orphan classes, no missing rules, no redefined utilities.

---

### 5. No Duplication — Single Shared Fetch Helper

`_refreshContextPct(tabId)` is defined once (chat.js:1922) and called from:
1. `_activateTab()` — immediate fetch on tab activation (AC6)
2. `_startContextPoll()` — `setInterval` every 5000 ms during streaming

No fetch logic is duplicated. The 5-second poll interval is unchanged from the
pre-existing design (the design deliberately does not poll while idle).

---

### 6. Edge Cases — Backend Omits, Frontend Hides

| Scenario | Backend behaviour | Frontend behaviour |
|----------|-------------------|--------------------|
| No assistant message with tokens | Returns `None`; `get_tab` does not inject `context_pct` | `_applyContextPct(NaN)` → hidden, empty text |
| Unknown model context window | `lookup_context_window` returns `None`; `get_tab` does not inject | Same as above |
| Runtime unavailable / HTTP failure | `contextlib.suppress(Exception)` swallows; no `context_pct` | Silent `.catch()` — no error shown |
| No active tab | N/A (no session object) | `_refreshContextPct(null)` → `_applyContextPct(NaN)` → hidden |
| `NaN` / missing from API | N/A | `_applyContextPct(NaN)` → hidden |
| `context_pct` = 0 | **Omitted** (used_tokens must be > 0 to inject) | No `0%` rendered |

No `0%` is ever rendered for "no data" — correct per design.

---

### 7. No New Poll Round-Trip Cost

`_providers_cache` (chat.py:619–630) mirrors the existing `_config_cache` pattern.
TTL is 30 s (`_PROVIDERS_TTL = 30.0`). `get_tab` calls
`_get_providers_cached(client)` once per request; `lookup_context_window` is pure
in-memory dict traversal. No uncached HTTP call per 5-second poll.

---

### 8. Scope — All Changed Files Within Impacted Paths

| File | In Impacted Paths? | Verified |
|------|-------------------|---------|
| `orch/chat/context_usage.py` | ✅ | New helper module — pure, no I/O |
| `dashboard/routers/chat.py` | ✅ | `get_tab` injection + `_get_providers_cached` |
| `dashboard/templates/chat_assistant/composer.html` | ✅ | Single `<span>` added |
| `dashboard/static/chat_assistant/chat.css` | ✅ | 4 rules appended (base, is-warn, is-crit, dark-mode) |
| `dashboard/static/chat_assistant/chat.js` | ✅ | `_refreshContextPct`, `_applyContextPct`, poll wiring |
| `tests/unit/test_context_usage.py` (untracked) | ✅ | 32 tests |
| `tests/dashboard/test_chat_context_pct_template.py` (untracked) | ✅ | 11 tests |
| `tests/integration/test_chat_tabs_api.py` | ✅ | 3 new context_pct integration tests |
| `tests/integration/_fake_opencode.py` | ✅ | Supports integration test seed data |

No DB schema change, no new/removed endpoints.

---

### 9. Regression — Unchanged Controls Still Correct

| Control | Still present? | Position correct? |
|---------|---------------|------------------|
| Model bar | ✅ | Unchanged (`_updateTabModelBar`) |
| Clear button | ✅ | Right of context % label |
| Abort button | ✅ | After Clear |
| Send button | ✅ | After Abort |
| `_updateClearButton()` | ✅ | Called after tab activation |
| `get_tab` return shape | ✅ | `{tab, session, messages}` preserved |

---

### 10. Conventions

| Convention | Status | Notes |
|------------|--------|-------|
| `dashboard/CLAUDE.md` | ✅ | Router stays thin; arithmetic in `context_usage.py` |
| `orch/CLAUDE.md` | ✅ | Pure helper; no DB/HTTP in `context_usage.py` |
| `chat.css` appended (not `styles.css`) | ✅ | Rules appended to `chat_assistant/chat.css` |
| IDs prefixed `chat-assistant-` | ✅ | `chat-assistant-context-pct` |
| Jinja2 `%`-style format filters | ✅ | No `str.format`-style usage in chat CSS/JS |
| No Docker usage | ✅ | Policy compliant |
| No migrations | ✅ | Policy compliant |

---

### 11. Test Results

| Suite | Result |
|-------|--------|
| `make lint` (ruff check) | ✅ All checks passed |
| `make format-check` | ⚠️ 2 pre-existing whitespace suggestions (unrelated files, not CR-00067) |
| `uv run pytest tests/unit/test_context_usage.py` | ✅ 32 passed |
| `uv run pytest tests/dashboard/test_chat_context_pct_template.py` | ✅ 11 passed |
| `uv run pytest tests/integration/test_chat_tabs_api.py -k context` | ✅ 3 passed |

Coverage threshold (50%) is a pre-existing project-wide gap (4.27% overall).
CR-00067 files achieve 90%+ individually. This is not a regression.

---

## Findings Summary

| # | Severity | Area | Finding |
|---|----------|------|---------|
| 1 | MEDIUM_SUGGESTION | Tests | `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py` — whitespace reformat of a comment tuple (CR-00065 side-effect, unrelated to CR-00067) |
| 2 | MEDIUM_SUGGESTION | Tests | `tests/integration/test_dashboard_remaining.py` — blank-line insertion before `import re` (CR-00065 side-effect, unrelated to CR-00067) |

**Mandatory fix count**: 0
**Verdict**: pass

---

## Notes

- The `make format-check` failure is on 2 files that have no functional relationship
  to CR-00067 (they are CR-00065 integration test fixtures). Both are
  whitespace-only changes. The linter (`make lint` / ruff check) passes cleanly
  on all files, including these two.
- All 46 targeted tests pass. The test files (`test_context_usage.py`,
  `test_chat_context_pct_template.py`) are untracked because S01/S02 committed
  only the implementation files; they will be included in the squash-merge.
- The `_providers_cache` 30-second TTL is a deliberate freshness trade-off:
  model `limit.context` values change rarely (only when the model list is
  reconfigured), so a 30-second cache avoids 1 HTTP call per 5-second poll
  without meaningfully degrading accuracy.
- Pi runtime graceful degradation is confirmed: `PiRuntime.get_session()` returns
  only `{"id", "pi_session_path"}` — `isinstance(session, dict)` is True, but
  `context_usage.resolve_model_from_tab` finds no provider/model info, so
  `context_pct` is never injected and the frontend label stays hidden. Correct
  per the design's documented Pi limitation.
