# I-00120 S06: Code Review — S05 (Tests)

**Reviewer**: CodeReview  
**Work Item**: I-00120  
**Step Reviewed**: S05 (Tests implementation)  
**Verdict**: `pass` — 1 fix applied inline during review

---

## Pre-Gate Results

| Check | Result |
|-------|--------|
| `make lint` | ✅ PASS — no violations |
| `make format` | ✅ PASS — all files formatted |
| `ruff check` changed files | ✅ PASS — no violations |

---

## Test Verification

```bash
uv run pytest tests/unit/test_llm_usage.py::TestOAuthIsExpired -v
```

| Test | Result |
|------|--------|
| `TestOAuthIsExpired::test_expired_in_past` | ✅ PASS |
| `TestOAuthIsExpired::test_expired_exactly_now` | ✅ PASS |
| `TestOAuthIsExpired::test_not_expired_in_future` | ✅ PASS |
| `TestOAuthIsExpired::test_missing_expires_returns_false` | ✅ PASS |
| `TestOAuthIsExpired::test_non_numeric_expires_returns_false` | ✅ PASS (fixed by S06 review) |

**Fix applied during review** (S06-001): changed `is False` → `is True` on line 1729 — `0.0` is a numeric float, so the implementation's `isinstance` guard passes and the epoch-0 comparison always yields `True`.

Full Codex suite (codex-filtered): **38 passed**.  
Full suite (`test_llm_usage.py` + `test_usage_fragment.py`): **114 passed, 0 failed**.

---

## Finding Fixed Inline

### S06-001 | MEDIUM_FIXABLE | Fixed inline during review

**File**: `tests/unit/test_llm_usage.py`, line 1729  
**Title**: `test_non_numeric_expires_returns_false` — incorrect expected value for `{"expires": 0.0}`

**Root cause**: The test declared `{"expires": 0.0}` to be a "non-numeric" case and asserted `is False`. However, the implementation is:

```python
def _oauth_is_expired(entry: dict[str, Any]) -> bool:
    raw = entry.get("expires")
    if not isinstance(raw, (int, float)):
        return False
    return raw <= datetime.now(UTC).timestamp() * 1000
```

`0.0 isinstance(float)` is `True`, so the guard is bypassed, and `0.0 <= now_ms` (epoch-1970 << now) always evaluates `True`.

**Fix applied**: `assert llm_usage._oauth_is_expired({"expires": 0.0}) is True`

**Why MEDIUM_FIXABLE not CRITICAL**: the assertion was introduced by S05 in the same commit — not a regression of pre-existing code.

---

## What Was Done Well

### ✅ Named reproduction test present and correct

`test_codex_usage_expired_token_reports_expired_status` exists directly in `test_llm_usage.py`. It monkeypatches `_load_openai_oauth` to return a token with `expires=1` (epoch-ms = 1ms into epoch), calls `_codex_usage()`, and asserts `result["status"] == "expired"`. This tests the proactive expiry path before any network call.

### ✅ `TestCodexStatusDiscriminator` covers all four statuses with SPECIFIC value assertions

Each test asserts `result.get("status") == "<specific-value>"` for all four states:

| Test | Status | Trigger |
|------|--------|---------|
| `test_expired_token_proactive_yields_expired_status` | `"expired"` | `expires=1` proactive; asserts no network calls |
| `test_401_response_yields_expired_status` | `"expired"` | `httpx.HTTPStatusError` + `Fake401Response()` |
| `test_unauthenticated_yields_unauthenticated_status` | `"unauthenticated"` | empty temp home dir |
| `test_non_401_http_error_yields_error_status` | `"error"` | HTTP 500 via `Fake500Response()` |
| `test_ok_response_yields_ok_status` | `"ok"` | valid fixture + future-expiry token |
| `test_outer_fallback_in_get_llm_usage_yields_error_status` | `"error"` | `_codex_usage` raises → outer fallback |

### ✅ `_oauth_is_expired` boundary table covered (5/5 cases, post-fix)

Past, exactly-now, future, missing, non-numeric (string + None + float) — all five cases pass after the inline fix.

### ✅ No network I/O in any unit test

Every test monkeypatches `httpx.get` and/or `Path.home` and/or `_load_openai_oauth`. No test reaches `https://chatgpt.com/backend-api/wham/usage`.

### ✅ `TestCodexUsageNeverRaises` — `_codex_usage()` is provably non-raising on all four error paths

Each scenario (oauth-None, proactive expiry, `ConnectTimeout`, JSON decode error) asserts `isinstance(result, dict)` and `"status" in result`. Strong guard against future regressions.

### ✅ Dashboard rendering tests use attribute-scoped assertions

- `TestCodexFragmentExpired`: `"token expired"` phrase AND `"re-authenticate"` phrase AND `"text-amber-600"` class AND absence of `"w-20"` bar containers
- `TestCodexFragmentOk`: warning absent (`"⚠"` not in section, `"text-amber-600"` not in section)
- `TestCodexFragmentError`: `"usage unavailable"` phrase
- `TestCodexFragmentUnauthenticated`: `"not configured"` AND `"opencode auth login"` phrases

### ✅ 401 → "expired" at WARNING level (not ERROR)

`test_handles_http_error_401_logs_warning` in `TestCodexUsage` explicitly asserts WARNING log, correctly distinguishing "token expired" from "usage unavailable" (error).

---

## Notes & Observations

### Note 1: Regex-based bar-exclusion in `TestCodexFragmentExpired` is fragile but acceptable

The test strips the warning `<span>` via regex before asserting `"w-20" not in codex_bars_only`. This depends on regex correctly matching the HTML structure. Acceptable — it tests the right behavior and passes.

### Note 2: No live DB usage

All dashboard tests use the `TestClient` fixture with `db_session` override. No test hits port 5433.

### Note 3: `importlib.reload` pattern is correctly scoped

All reloads (`TestCacheTTL`, `TestGetLlmUsageCodexIntegration`) re-apply monkeypatches after reload and target `pathlib.Path.home`, not `orch.config`.

### Note 4: "shape-only" assertion check

The `test_ok_status_shows_bars_and_no_warning` rendering test uses `"width:" in codex_section` for the bar check (not a CSS class), plus the explicit absence checks for `"text-amber-600"` and `"⚠"`. This is acceptable — the CSS class check for amber is present, and the bar-exists check is complemented by the explicit absence-of-warning pair.

---

## Review Summary

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00120",
  "step_reviewed": "S05",
  "verdict": "pass",
  "findings": [
    {
      "id": "S06-001",
      "severity": "MEDIUM_FIXABLE",
      "file": "tests/unit/test_llm_usage.py",
      "location": "TestOAuthIsExpired::test_non_numeric_expires_returns_false, line 1729",
      "title": "Incorrect expected value: 0.0 is NOT a non-numeric sentinel",
      "body": "The test declared {'expires': 0.0} to be non-numeric and asserted is False, but float 0.0 passes isinstance check so the implementation evaluates epoch-0 <= now_ms → True (always expired).",
      "fix": "Changed is False to is True.",
      "status": "fixed_inline"
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "114 passed, 0 failed",
  "notes": "1 × MEDIUM_FIXABLE fixed inline. Lint and format gates clean. All four Codex statuses covered with specific assertions. No network I/O. Dashboard tests attribute-scoped."
}
```
