# CR-00043 S05 — Tests Implementation Report

## What was done

Created `tests/dashboard/test_markdown_chromium.py` with unit tests for `_resolve_chromium_binary()` and its integration with `render_pdf_chromium`.

## Test cases added (10 total)

| Test | AC | Description |
|------|----|-------------|
| `test_env_override_wins` | AC1 | `IW_PLAYWRIGHT_CHROME_PATH` pointing at existing executable is returned, bypassing cache and PATH |
| `test_env_override_nonexistent_is_ignored` | AC1 | Env var set to non-existent path falls through to ms-playwright cache |
| `test_ms_playwright_glob_picks_newest` | AC2 | With multiple `chromium-*` dirs, the highest-numbered one with a real `chrome` binary wins |
| `test_ms_playwright_skips_incomplete_dirs` | AC2 | A `chromium-*` dir missing `chrome-linux64/chrome` is silently skipped |
| `test_path_lookup_fallback` | AC3 | When env and cache both absent, `shutil.which` result is returned |
| `test_path_lookup_tries_names_in_order` | AC3 | `which` is called in order: `chromium` → `chromium-browser` → `google-chrome` |
| `test_path_lookup_none_when_nothing_found` | AC3 | Returns `None` when all three methods fail |
| `test_render_pdf_chromium_returns_none_when_unresolved` | AC4 | With `_PLAYWRIGHT_CHROME = None`, `render_pdf_chromium` returns `None` gracefully |
| `test_render_pdf_chromium_returns_none_when_path_missing` | AC4 | With `_PLAYWRIGHT_CHROME` pointing to non-existent file, returns `None` gracefully |

## AC Coverage

- **AC1** ✅ — Tests `test_env_override_wins` + `test_env_override_nonexistent_is_ignored`
- **AC2** ✅ — Tests `test_ms_playwright_glob_picks_newest` + `test_ms_playwright_skips_incomplete_dirs`
- **AC3** ✅ — Tests `test_path_lookup_fallback` + `test_path_lookup_tries_names_in_order` + `test_path_lookup_none_when_nothing_found`
- **AC4** ✅ — Tests `test_render_pdf_chromium_returns_none_when_unresolved` + `test_render_pdf_chromium_returns_none_when_path_missing`

## Files changed

- **Created**: `tests/dashboard/test_markdown_chromium.py` (216 lines, 10 test cases)
- **No changes** to `tests/dashboard/test_docs_pdf_chromium.py` — it was already compatible (it mocks `render_pdf_chromium` and monkeypatches `_PLAYWRIGHT_CHROME`, which still works with the new `Path | None` type)

## Test results

```
uv run pytest tests/dashboard/test_markdown_chromium.py tests/dashboard/test_docs_pdf_chromium.py -q --no-cov
19 passed, 1 warning in 8.69s
```

## Quality checks

- `make lint` — All checks passed (ruff)
- `make format-check` — All checks passed (ruff format)
- `make type-check` — Success: no issues found in 240 source files