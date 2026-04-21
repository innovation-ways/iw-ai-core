# I-00033 S04 Code Review Report

## Summary

Reviewed S03 (tests-impl) output for I-00033 Code view layout bugs. **Verdict: PASS** — zero critical, zero high findings.

---

## RED Phase Verification

Confirmed RED via `git stash push` on S01's 5 modified files, running tests, confirming all 4 failures, then `git stash pop` to restore and confirm all 4 pass:

| Test | Pre-S01 (RED) | Post-S01 (GREEN) |
|------|---------------|------------------|
| `test_last_run_banner_has_dismiss_button` | FAIL — no dismiss button | PASS |
| `test_code_content_root_does_not_own_scroll` | FAIL — `#code-content-root` has `lg:overflow-y-auto` | PASS |
| `test_page_body_has_gap_4` | FAIL — `#page-body` has `gap-0`, no `lg:gap-4` | PASS |
| `test_architecture_card_owns_scroll` | FAIL — card has `overflow-hidden`, no `h-full` or `overflow-y-auto` | PASS |

---

## Checklist Assessment

### Semantic correctness (I003 lesson)

| Item | Status | Notes |
|------|--------|-------|
| `data-dismiss-job-id="12345"` assertion | ✅ | Line 55 checks full literal string with `=` and specific value |
| `--chat-width` assertion equals `"48px"` | ✅ | Browser test line 135 checks exact string `"48px"` |
| `overflow-y-auto` absence scoped to `#code-content-root` | ✅ | Line 96: only the `#code-content-root` opening tag block is checked |
| Architecture card scroll requires `h-full` | ✅ | Line 140: explicit `h-full` assertion with explanation |
| `overflow-hidden` removal checked | ✅ | Line 145: explicit check that `overflow-hidden` is not present |

### RED-phase verification

- ✅ S03 report documents RED phase via `git stash` method
- ✅ All 4 tests actually failed against pre-S01 code

### Fixture hygiene

| Item | Status | Notes |
|------|--------|-------|
| Browser tests use `dashboard_server` / `playwright_session` fixtures | ✅ | `tests/dashboard/browser/conftest.py` module-scoped fixtures shared with `test_chat_panel_smoke.py` |
| No duplicated Uvicorn boot logic | ✅ | `dashboard_server` lives in conftest only; `test_chat_panel_smoke.py` still has its own copy (unmodified in S03) |
| localStorage cleared between tests | ✅ | `autouse` module-scoped teardown fixture at line 101-118 |
| No CodeIndexJob seed fixture added | ✅ | Bug 1 browser test skips cleanly when no banner is present |

### Browser test discipline

| Item | Status | Notes |
|------|--------|-------|
| Uses `playwright-cli` exclusively | ✅ | All interactions via `subprocess.run(["playwright-cli", ...])` |
| `@pytest.mark.browser` applied | ✅ | `pytestmark = pytest.mark.browser` at module level (line 16) |
| Snapshot called before click/fill | ✅ | Bug 1 test calls `_snap(session)` before `click` |
| No hardcoded URL | ✅ | Uses `dashboard_server` fixture base URL |

### Test readability

| Item | Status | Notes |
|------|--------|-------|
| Docstrings name the specific bug | ✅ | Each test class has a descriptive docstring referencing I-00033 |
| Failure messages are informative | ✅ | e.g., line 136: `f"Expected --chat-width=48px on collapse, got {val!r} (I-00033 bug 3)"` |

### No violations of tests/CLAUDE.md

| Item | Status |
|------|--------|
| No `importlib.reload(orch.config)` | ✅ |
| No direct connection to port 5433 | ✅ |
| No mocking of DB in integration tests | ✅ |
| No writes to tracked config files | ✅ |

### Coverage of the three bugs

| Bug | Render test | Browser test | Notes |
|-----|-------------|--------------|-------|
| Bug 1 (banner dismissal) | `test_last_run_banner_has_dismiss_button` | `test_bug1_last_run_banner_dismissal_persists` | Both present |
| Bug 2 (scroll container) | `test_code_content_root_does_not_own_scroll` + `test_architecture_card_owns_scroll` | `test_bug2_scroll_container_is_architecture_card` | Both present |
| Bug 3 (chat collapse) | — (CSS variable runtime JS) | `test_bug3_chat_collapse_shrinks_grid_track` | Browser test sufficient |

---

## Quality Checks

| Command | Result |
|---------|--------|
| `uv run ruff check tests/dashboard/test_code_layout_fixes.py tests/dashboard/browser/test_code_layout_fixes.py tests/dashboard/browser/conftest.py` | PASS |
| `uv run ruff format --check ...` | PASS (3 files already formatted) |
| `uv run pytest tests/dashboard/test_code_layout_fixes.py -v` | 4 passed |

---

## Notes

### conftest.py creation vs fixture duplication

S03 created `tests/dashboard/browser/conftest.py` (new file) to hold shared fixtures. However, `test_chat_panel_smoke.py` still has its own duplicate `dashboard_server` and `playwright_session` definitions at lines 21–68. This is **not an S03 regression** — S03 only created `conftest.py`; it did not modify `test_chat_panel_smoke.py`. The duplication is a pre-existing issue in the codebase and outside the scope of this review. The new test file correctly imports nothing and relies entirely on conftest fixtures.

### Bug 3 browser test only

Bug 3 (chat collapse) is a runtime JavaScript CSS variable bug. The browser test at `test_bug3_chat_collapse_shrinks_grid_track` verifies `--chat-width` equals `"48px"` after collapse and is restored after expand. No unit-level CSS variable contract test exists — this is acceptable per the design doc which states "a browser test is sufficient" for bug 3.

---

## Subagent Result

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00033",
  "reviews_step": "S03",
  "verdict": "pass",
  "findings": [],
  "notes": "All 4 Jinja render tests verified RED (failed against pre-S01 via git stash) and GREEN (pass after restore). Browser tests correctly use playwright-cli, autouse localStorage teardown, module-scoped fixtures from conftest.py. No CLAUDE.md violations. Bug 1+2 have render+browser coverage; bug 3 has browser-only coverage (acceptable per design doc). ruff clean, formatting clean."
}
```