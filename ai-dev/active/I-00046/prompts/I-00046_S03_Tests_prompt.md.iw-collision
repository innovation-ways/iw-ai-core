# I-00046_S03_Tests_prompt

**Work Item**: I-00046 — Code view chat panel — toggle button clipped and viewport drift on module select
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations in this fix.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00046 --json`
- `ai-dev/active/I-00046/I-00046_Issue_Design.md` — design document with reproduction tests
- `ai-dev/active/I-00046/reports/I-00046_S01_Frontend_report.md` — S01 implementation report
- `dashboard/templates/project_code.html` — fixed by S01
- `dashboard/templates/chat/panel.html` — fixed by S01
- `tests/dashboard/test_code_layout_fixes.py` — reference: existing structural template tests (I-00033)
- `tests/dashboard/conftest.py` — check for shared fixtures
- `tests/conftest.py` — root conftest

## Output Files

- `tests/dashboard/test_chat_panel_layout_i00046.py` — new reproduction + regression test file
- `ai-dev/active/I-00046/reports/I-00046_S03_Tests_report.md` — step report

## Context

Write structural template tests that verify the two I-00046 fixes. These tests must:
1. FAIL against the pre-fix templates (proving they detect the bug)
2. PASS against the post-fix templates (proving the fix is correct)

The pattern follows `tests/dashboard/test_code_layout_fixes.py` — pure Jinja rendering,
no browser, no server, fast unit tests.

---

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "min-h-0" in html` (shape — could match anywhere in page)
- GOOD: `assert "min-h-0" in root_match.group(0)` (semantic — verifies the specific element)
- GOOD: `assert "overflow-hidden" not in aside_tag` (semantic — verifies the unwanted class is absent from the specific aside)
- GOOD: `assert count == 1` (semantic — verifies exactly one occurrence of the ID)

**Every assertion must target the specific element, not the whole page HTML.**

---

## Requirements

### 1. Create `tests/dashboard/test_chat_panel_layout_i00046.py`

Model after `tests/dashboard/test_code_layout_fixes.py`. Use the same Jinja environment
fixture pattern (or reference the shared fixture if it exists in `conftest.py`).

**Required test classes and methods:**

#### `TestChatPanelToggleButton` — Bug (a): toggle button clip fix

```python
class TestChatPanelToggleButton:
    """I-00046 bug (a): toggle button must not be clipped by aside overflow-hidden."""

    def test_no_duplicate_chat_panel_slot_id(self, jinja_env):
        """id='chat-panel-slot' must appear exactly once in the rendered page.

        FAILS before fix: panel.html wraps content in <div id='chat-panel-slot'>,
        creating a duplicate alongside the outer <aside id='chat-panel-slot'>.
        PASSES after fix: inner wrapper's ID is removed.
        """
        html = _render_code_page(jinja_env)
        count = html.count('id="chat-panel-slot"')
        assert count == 1, (
            f"Expected exactly 1 element with id='chat-panel-slot', found {count}. "
            "Duplicate IDs break JS getElementById and constitute a DOM violation "
            "(I-00046 bug a)."
        )

    def test_aside_does_not_have_overflow_hidden(self, jinja_env):
        """The <aside id='chat-panel-slot'> must NOT have overflow-hidden.

        FAILS before fix: aside has lg:overflow-hidden which clips the toggle button
        that extends at left:-48px.
        PASSES after fix: overflow-hidden removed.
        """
        html = _render_code_page(jinja_env)
        aside_match = re.search(r'<aside[^>]+id="chat-panel-slot"[^>]*>', html)
        assert aside_match, "Could not find <aside id='chat-panel-slot'> in rendered HTML"
        aside_tag = aside_match.group(0)
        assert "overflow-hidden" not in aside_tag, (
            "<aside id='chat-panel-slot'> must not have overflow-hidden — "
            "it clips the toggle button positioned at left:-48px (I-00046 bug a)"
        )

    def test_aside_has_min_h_0(self, jinja_env):
        """The <aside id='chat-panel-slot'> must have lg:min-h-0.

        FAILS before fix: aside lacks min-h-0.
        PASSES after fix.
        """
        html = _render_code_page(jinja_env)
        aside_match = re.search(r'<aside[^>]+id="chat-panel-slot"[^>]*>', html)
        assert aside_match, "Could not find <aside id='chat-panel-slot'> in rendered HTML"
        aside_tag = aside_match.group(0)
        assert "min-h-0" in aside_tag, (
            "<aside id='chat-panel-slot'> must have min-h-0 so the chat column "
            "respects its CSS grid row size (I-00046 bug a/c)"
        )

    def test_toggle_tab_button_is_present(self, jinja_env):
        """#chat-toggle-tab button must exist in the rendered page.

        Regression guard: ensure the toggle button was not accidentally removed
        while fixing the duplicate ID issue.
        """
        html = _render_code_page(jinja_env)
        assert 'id="chat-toggle-tab"' in html, (
            "#chat-toggle-tab button must be present in the rendered page — "
            "it is the primary collapse/expand control (I-00046 regression guard)"
        )
        assert 'left: -48px' in html, (
            "Toggle button must retain style='left: -48px' so it visually "
            "protrudes from the chat panel's left edge (I-00046 regression guard)"
        )
```

#### `TestCodeContentRootContainment` — Bug (c): grid row containment

```python
class TestCodeContentRootContainment:
    """I-00046 bug (c): #code-content-root must contain the CSS grid row."""

    def test_code_content_root_has_min_h_0(self, jinja_env):
        """#code-content-root must have lg:min-h-0.

        FAILS before fix: no class attribute on #code-content-root, so it lacks
        min-h-0 and can grow the 1fr grid row beyond the viewport.
        PASSES after fix.
        """
        html = _render_code_page(jinja_env)
        root_match = re.search(r'<div[^>]+id="code-content-root"[^>]*>', html)
        assert root_match, "Could not find #code-content-root in rendered HTML"
        root_tag = root_match.group(0)
        assert "min-h-0" in root_tag, (
            "#code-content-root must have min-h-0 so the CSS grid 1fr row is not "
            "expanded by module detail content beyond the viewport (I-00046 bug c)"
        )
```

**Helper function** (module-level, not a test):

```python
def _render_code_page(jinja_env):
    """Render project_code.html with minimal context for layout tests."""
    mock_request = MagicMock()
    mock_request.url.path = "/project/iw-ai-core/code"
    tpl = jinja_env.get_template("project_code.html")
    return tpl.render(
        current_project=type("P", (), {"id": "iw-ai-core", "display_name": "IW"})(),
        index_status=None,
        running_job=None,
        last_completed_job=None,
        last_completed_recent=False,
        content_html="<p>x</p>",
        request=mock_request,
    )
```

### 2. Jinja Environment Fixture

Check if `tests/dashboard/conftest.py` already exports a `jinja_env` fixture compatible
with the one in `tests/dashboard/test_code_layout_fixes.py`. If so, use the shared
fixture (import from conftest or use pytest's fixture resolution).

If not, copy the fixture from `test_code_layout_fixes.py` into the new test file. The
fixture needs these custom filters:
- `intcomma` — formats integers with commas
- `timeago` — returns empty string
- `fmt_ts_time` — returns empty string
- `localdt` — returns empty string
- `url_for` global stub
- `is_db_stale` global stub

### 3. Verify TDD RED phase

After writing the tests but **before any fix is applied**, confirm the tests fail:

```bash
uv run pytest tests/dashboard/test_chat_panel_layout_i00046.py -v 2>&1 | head -40
```

At this point S01 has already applied the fix, so the tests should PASS. Document in the
report that you verified what the pre-fix failures would look like by reading the design
document's root cause analysis, and that the tests semantically cover the exact symptoms.

### 4. Run full dashboard test suite

```bash
make test-unit
```

All tests in `tests/dashboard/` must pass, including:
- The new `test_chat_panel_layout_i00046.py` tests (should all PASS post-fix)
- The existing `test_code_layout_fixes.py` tests (must not regress I-00033)
- All other dashboard tests

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. **`make format`** — check Python formatting; fix any ruff issues in the new test file
2. **`make typecheck`** — zero mypy errors in the new test file
3. **`make lint`** — must pass

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00046",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_chat_panel_layout_i00046.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Note whether jinja_env fixture was shared or copied, and confirm RED phase analysis"
}
```
