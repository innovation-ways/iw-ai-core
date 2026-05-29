# I-00120_S05_Tests_report — Reproduction + Regression Tests for Codex Status Discriminator

**Work Item**: I-00120 — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Step**: S05
**Agent**: tests-impl
**Completion**: complete

---

## What Was Done

Implemented the full test suite for I-00120, covering both the backend status-discriminator logic and the dashboard fragment's rendering of the warning states.

### Files Changed

| File | Change |
|------|--------|
| `tests/unit/test_llm_usage.py` | Added `TestOAuthIsExpired`, `TestCodexUsageNeverRaises`, `test_codex_usage_expired_token_reports_expired_status` standalone reproduction test, and an updated module docstring |
| `tests/dashboard/test_usage_fragment.py` | **New** — 5 rendering regression tests driven by `TestClient` against `GET /api/usage/llm/fragment`, covering all four Codex warning states plus the ok state |

---

## Test Coverage Summary

### Backend (`tests/unit/test_llm_usage.py`)

| Class / Test | What it covers |
|---|---|
| `TestOAuthIsExpired` (5 cases) | Boundary table: `expires` in past → `True`; exactly now → `True`; in future → `False`; missing → `False`; non-numeric/None → `False` |
| `test_codex_usage_expired_token_reports_expired_status` | Direct monkeypatch of `_load_openai_oauth` with `expires=1`; asserts `status == "expired"` and `block_pct == 0` — TDD red/green baseline |
| `TestCodexUsageNeverRaises` (4 cases) | `_codex_usage()` never raises for: oauth-None path, proactive expiry, network error, JSON decode error |
| `TestCodexStatusDiscriminator` (6 existing cases) | `ok`, `expired` (proactive + 401), `unauthenticated`, `error` (non-401 HTTP + outer fallback) — already present as green-path tests written after S01 |

### Dashboard (`tests/dashboard/test_usage_fragment.py`)

| Class / Test | Asserted HTML contract |
|---|---|
| `TestCodexFragmentExpired::test_expired_status_shows_warning_and_bars_absent` | `"token expired"` AND `"re-authenticate"` present; `text-amber-600` present; `w-20` bar containers absent |
| `TestCodexFragmentUnauthenticated::test_unauthenticated_status_shows_not_configured_warning` | `"not configured"` AND `"opencode auth login"` present; `text-amber-600` present |
| `TestCodexFragmentError::test_error_status_shows_usage_unavailable_warning` | `"usage unavailable"` present; `text-amber-600` present |
| `TestCodexFragmentOk::test_ok_status_shows_bars_and_no_warning` | Percentage bars present (`width:`); `⚠` absent; `text-amber-600` absent; no warning phrases |
| `TestCodexFragmentOk::test_ok_zero_pct_still_shows_bars_no_warning` | `width: 0%` bars present; no `⚠` or warning phrases |

**All assertions are semantic** (specific values, not shape-only checks), following the I003 lesson.

---

## Test Results

```
tests/unit/test_llm_usage.py -k codex  →  38 passed, 71 deselected
tests/dashboard/test_usage_fragment.py  →  5 passed
```

---

## Key Implementation Decisions

1. **Monkeypatch target for dashboard tests**: `dashboard.routers.usage.get_llm_usage` (not `orch.llm_usage.get_llm_usage`) because the router imports it directly. Using the orch path gave 4 false failures due to module-level caching.

2. **`dict[str, object]` return type** for fake `get_llm_usage`: avoids mypy "Missing type arguments" while staying permissive enough to construct the fake return dict inline with typed codex data.

3. **`text-amber-600` in expired/unauthenticated/error** (but not ok): attribute-scoped assertion, not a bare ambiguous substring — ensures the specific warning colour class is present.

4. **Bar containers (`w-20`) absent in warning states**: the Jinja2 template replaces BOTH bar divs with the warning `<span>` when `codex_warning` is truthy. The test strips the warning span using a regex before checking for bar absence, making the assertion precise.

---

## Notes

- The `_codex_usage()` status-discriminator tests (`TestCodexStatusDiscriminator`) were already added by the S05 author at the same time as the S01 fix — they pass cleanly because S01+frontend work is present in the worktree.
- mypy reports one pre-existing `Generator` return type on the `client` fixture (shared across all dashboard tests) and a `Fake*Response` attribute mismatch in the backend tests — both are pre-existing patterns, not introduced here.
- The 2-line ruff E501 fix is a mechanical truncation to ≤100 chars; all other ruff checks pass.
