# I-00070_S03_Tests_prompt

**Work Item**: I-00070 -- Copy paste prompt button silently fails over plain HTTP from a non-localhost hostname
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. No container operations are required for this step. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch Alembic migrations.

## Input Files

- `ai-dev/active/I-00070/I-00070_Issue_Design.md` — Design document (READ FIRST)
- `ai-dev/active/I-00070/reports/I-00070_S01_Frontend_report.md` — S01 fix report
- `ai-dev/active/I-00070/reports/I-00070_S02_CodeReview_Frontend_report.md` — S02 review report
- `dashboard/static/clipboard.js` — the helper under test
- `dashboard/templates/fragments/item_execution_report.html` — the rendered template containing the button
- `tests/dashboard/test_execution_report_self_assess.py` — the existing dashboard test pattern (TestClient + db_session + tmp_path) — use the same fixtures for the server-side test
- `tests/dashboard/browser/test_chat_scroll_i00060.py` — example Playwright test in this repo (use as a structural reference for the browser test)
- `tests/CLAUDE.md` — non-negotiable test rules

## Output Files

- `tests/dashboard/test_i00070_clipboard_fallback.py` — server-side fragment assertions
- `tests/dashboard/browser/test_i00070_clipboard_fallback.py` — Playwright fallback assertions
- `ai-dev/active/I-00070/reports/I-00070_S03_Tests_report.md` — Step report

## Context

You are writing the reproduction + regression tests for I-00070. The fix is already in. Your tests MUST:

1. Verify the buggy pattern (`navigator.clipboard.writeText` inline) is gone from the rendered output.
2. Verify the helper is wired in (rendered HTML references `iwClipboard.copy` or `data-iw-copy`).
3. Verify the helper's fallback branch actually copies and provides UI feedback when the clipboard API is unavailable (the precise scenario that fails on `iw-dev-01`).
4. Verify no `TypeError` reaches the browser console.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Apply the same standard here:
- BAD: `assert "<button" in html` (button exists — also true on the broken template)
- GOOD: `assert "navigator.clipboard.writeText" not in html` (specifically verifies the buggy pattern is absent)
- GOOD: `assert "iwClipboard.copy" in html or "data-iw-copy" in html` (specifically verifies the helper is wired)

## Requirements

### 1. Server-side test: `tests/dashboard/test_i00070_clipboard_fallback.py`

Use the existing fixture pattern from `tests/dashboard/test_execution_report_self_assess.py`. Reuse the helpers there if they're importable; otherwise duplicate the minimum needed (it's fine — the existing test file already contains a `_create_item_with_self_assess` helper).

```python
class TestI00070ClipboardFallback:
    def test_self_assess_button_does_not_use_inline_navigator_clipboard(
        self, client, db_session, test_project, tmp_path,
    ):
        """RED: would fail on the buggy template, PASSES after S01."""
        # Arrange
        item = _create_item_with_self_assess(
            db_session, test_project, tmp_path,
            findings_json=json.dumps({
                "findings": [{
                    "severity": "HIGH", "class": "x", "target": "iw-ai-core",
                    "title": "t", "recommendation": "r",
                    "paste_prompt": "/iw-new-cr SAMPLE_PROMPT_TOKEN",
                    "evidence": [],
                }],
            }),
        )

        # Act
        resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
        assert resp.status_code == 200
        html = resp.text

        # Assert (semantic correctness)
        assert "navigator.clipboard.writeText" not in html, (
            "Inline navigator.clipboard.writeText is back — the button will silently fail "
            "on http://iw-dev-01:9900 (non-secure context). Use window.iwClipboard.copy(...) instead."
        )
        assert "iwClipboard.copy" in html, "Button is not wired through the shared helper"
        # The full prompt is still embedded so the helper has something to copy
        assert "SAMPLE_PROMPT_TOKEN" in html

    def test_oss_install_modal_uses_helper(
        self, client, db_session, test_project, tmp_path,
    ):
        """Render any template fragment that previously contained inline
        navigator.clipboard.writeText and assert the migration is complete.
        Skip the test (with a clear reason) if the route is not reachable
        without complex setup — but at minimum, parse the .html source on
        disk and assert no inline navigator.clipboard.writeText remains."""
        from pathlib import Path
        for relpath in [
            "dashboard/templates/fragments/item_execution_report.html",
            "dashboard/templates/fragments/oss_cli_block.html",
            "dashboard/templates/fragments/oss_install_modal.html",
            "dashboard/templates/pages/project/oss.html",
            "dashboard/static/chat/actions.js",
            "dashboard/static/chat/render.js",
        ]:
            content = Path(relpath).read_text(encoding="utf-8")
            assert "navigator.clipboard.writeText" not in content, (
                f"{relpath} still contains a direct navigator.clipboard.writeText call"
            )

    def test_clipboard_helper_file_exists_and_exports_iwclipboard(self):
        """The shared helper file exists and exposes window.iwClipboard.copy."""
        from pathlib import Path
        helper = Path("dashboard/static/clipboard.js").read_text(encoding="utf-8")
        assert "window.iwClipboard" in helper
        # The fallback path must be present (text-area + execCommand)
        assert "execCommand" in helper
        assert "createElement('textarea')" in helper or 'createElement("textarea")' in helper
        # The helper must reject (not swallow) on failure
        assert "reject" in helper

    def test_base_html_loads_clipboard_js(self):
        """base.html loads the shared helper synchronously."""
        from pathlib import Path
        base = Path("dashboard/templates/base.html").read_text(encoding="utf-8")
        assert "/static/clipboard.js" in base
```

### 2. Playwright test: `tests/dashboard/browser/test_i00070_clipboard_fallback.py`

Mirror the structure of `tests/dashboard/browser/test_chat_scroll_i00060.py` (same fixtures / setup). Open the dashboard via `localhost`, then BEFORE clicking the button, monkey-patch the page so `window.isSecureContext` is `false` and `navigator.clipboard` is gone — this exactly simulates the `iw-dev-01` access mode in the test browser.

```python
def test_i00070_button_works_when_clipboard_api_is_unavailable(page, dashboard_url, db_session, test_project):
    # Arrange: navigate to a page that has the Self-Assessment Copy paste prompt button
    page.goto(f"{dashboard_url}/project/{test_project.id}/item/<test_item_id>")
    # Click into the Execution Report tab
    page.click('button:has-text("Execution Report")')
    page.wait_for_selector('button:has-text("Copy paste prompt")', timeout=5000)

    # Capture console messages
    console_messages = []
    page.on("console", lambda msg: console_messages.append(msg.text))

    # Strip the secure-context clipboard API to simulate iw-dev-01 plain-HTTP access
    page.evaluate("Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true });")
    page.evaluate("delete navigator.clipboard;")

    # Sanity: the helper now MUST take the fallback branch
    has_clipboard = page.evaluate("typeof navigator.clipboard !== 'undefined'")
    assert has_clipboard is False

    # Act
    page.click('button:has-text("Copy paste prompt")')

    # Assert (semantic correctness): the helper must surface success feedback
    page.wait_for_selector('button:has-text("Copied")', timeout=2000)

    # Assert: no TypeError ended up in the console
    type_errors = [m for m in console_messages if "TypeError" in m]
    assert type_errors == [], f"Unexpected TypeError(s): {type_errors}"
```

If `dashboard_url` / `dashboard_url`-style fixtures don't exist in this repo, follow the pattern from `tests/dashboard/browser/test_chat_scroll_i00060.py` for spinning up a test dashboard and seeding a work item with a self_assess step. The seeding helper from the server-side test is a good starting point.

### 3. Pre-flight quality gates

Before reporting `complete`:
1. `make format` — auto-fix.
2. `make typecheck` — zero errors involving touched files.
3. `make lint` — zero errors.
4. `make test-unit` and the new dashboard tests must pass on the fixed code.

Record each in the `preflight` block.

## Project Conventions

Read `tests/CLAUDE.md` for non-negotiable rules. Especially:

- NEVER connect to live DB. Use testcontainers for integration; `db_session` fixture for dashboard tests.
- Browser tests live under `tests/dashboard/browser/` and are typically opt-in.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00070",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_i00070_clipboard_fallback.py",
    "tests/dashboard/browser/test_i00070_clipboard_fallback.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Server-side tests verified to fail when navigator.clipboard.writeText is reintroduced into the template (manual sanity check)."
}
```
