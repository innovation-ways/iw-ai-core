# CR-00043 S06 — Code Review Report

**Agent**: code-review-impl
**Reviewed**: tests-impl (S05)
**Work Item**: CR-00043 — Robust Chromium resolution for dashboard PDF / Mermaid rendering in containers

---

## Summary

S05 (tests-impl) wrote `tests/dashboard/test_markdown_chromium.py` with 10 test cases covering all four ACs and several edge cases. The file is clean and well-structured. `tests/dashboard/test_docs_pdf_chromium.py` is unchanged (correctly — it mocks `render_pdf_chromium` and has no hardcoded path assertions to update).

---

## Files Reviewed

| File | Change | Verdict |
|------|--------|---------|
| `tests/dashboard/test_markdown_chromium.py` | New — 10 tests | **PASS** |
| `tests/dashboard/test_docs_pdf_chromium.py` | No changes | **N/A** |

---

## Test Results

```
uv run pytest tests/dashboard/test_markdown_chromium.py tests/dashboard/test_docs_pdf_chromium.py -q
19 passed, 1 warning in 21.74s
```

Coverage failure is a pre-existing repo-wide threshold issue (18.85% < 46% required) — unrelated to these tests.

---

## AC Coverage

| AC | Description | Tests | Covered |
|----|-------------|-------|---------|
| AC1 | Env var override wins | `test_env_override_wins`, `test_env_override_nonexistent_is_ignored` | ✓ |
| AC2 | ms-playwright glob picks newest, skips incomplete dirs | `test_ms_playwright_glob_picks_newest`, `test_ms_playwright_skips_incomplete_dirs` | ✓ |
| AC3 | PATH fallback with correct name order | `test_path_lookup_fallback`, `test_path_lookup_tries_names_in_order`, `test_path_lookup_none_when_nothing_found` | ✓ |
| AC4 | Graceful degradation when unresolved | `test_render_pdf_chromium_returns_none_when_unresolved`, `test_render_pdf_chromium_returns_none_when_path_missing` | ✓ |

---

## Quality Gate Results

| Check | Result |
|-------|--------|
| `make lint` | All checks passed |
| `make format-check` | 667 files already formatted |
| `make type-check` | Success: no issues found in 240 source files |

---

## Review Checklist

### Isolation
- **No real host filesystem accessed**: All tests use `tmp_path` for fake chrome and fake ms-playwright cache. `Path.home` is monkeypatched in every test.
- **No real `shutil.which` called**: All tests mock `dashboard.utils.markdown.shutil.which` with `patch`.
- **No real Chromium subprocess**: The `render_pdf_chromium` tests patch `_PLAYWRIGHT_CHROME` directly or set it to a `tmp_path` that never gets a real Chromium binary.

### DB-bound module imports
- `test_markdown_chromium.py` imports only `dashboard.utils.markdown` — not `dashboard.routers.*` or `dashboard.dependencies`. ✓
- `test_docs_pdf_chromium.py` uses the `client` fixture with `db_session` (correctly) and `monkeypatch` on `_PLAYWRIGHT_CHROME` — no DB issues.

### `importlib.reload(orch.config)`
- Not used in either test file. ✓

### Assertion semantics
- `test_env_override_wins`: `assert result == env_chrome` — semantic, not just "doesn't crash". ✓
- `test_ms_playwright_glob_picks_newest`: `assert result == chrome_1220` — verifies the correct newest path is picked. ✓
- `test_path_lookup_tries_names_in_order`: `assert calls == ["chromium", "chromium-browser", "google-chrome"]` — verifies name order, also implicitly verifies `google-chrome-stable` is **not** called (stops on first match). ✓
- `test_ms_playwright_skips_incomplete_dirs`: `assert result is None` — verifies fallback to `which`, then `None`. ✓
- AC4 tests: `assert result is None` (not `assert result is not False` or similar). ✓

### Edge cases
- **Non-existent env path falls through**: `test_env_override_nonexistent_is_ignored` covers AC1's second clause. ✓
- **Incomplete chromium dir (no `chrome-linux64/chrome`) is skipped**: `test_ms_playwright_skips_incomplete_dirs`. ✓
- **`which` stops on first match**: `test_path_lookup_tries_names_in_order` asserts `google-chrome-stable` is never tried. ✓

### Name order per AC3
The design doc specifies `chromium`, `chromium-browser`, `google-chrome`, `google-chrome-stable`. The implementation matches this order in `markdown.py:78`. The test asserts `calls == ["chromium", "chromium-browser", "google-chrome"]` and verifies `google-chrome-stable` is not tried — correct.

---

## Findings

None. All tests pass, all ACs are covered, no real host binaries or DB-bound modules are touched.

---

## Verdict

```
PASS
mandatory_fix_count: 0
findings: []
```

All S05 tests are correct, isolated, and semantically assertions. No issues found.