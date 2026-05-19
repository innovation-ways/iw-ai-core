# I-00094_S03_Tests_prompt

**Work Item**: I-00094 — Auto-merge htmx-only `<a>` tags render with text cursor and bad accessibility
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00094 --json`
- `ai-dev/active/I-00094/I-00094_Issue_Design.md`
- `ai-dev/active/I-00094/reports/I-00094_S01_Frontend_report.md`
- The three modified fragment templates (post-S01)
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`
- `tests/dashboard/conftest.py`

## Output Files

- `ai-dev/active/I-00094/reports/I-00094_S03_Tests_report.md`

## Context

S01 converted every `<a hx-get>` without `href` into a
`<button type="button" hx-get>`. You write the assertions that lock
this in.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

- BAD: `assert "button" in html` (the word appears in many places —
  buttons, labels, etc.)
- BAD: `assert "<button" in html` (passes against a partial fix; says
  nothing about the specific chips)
- GOOD: Use a regex that finds `<a hx-get="…/auto-merge/…">` WITHOUT
  `href=` — assert the regex finds zero matches.
- GOOD: Use a regex that finds `<button type="button" … hx-get="…">`
  — assert at least N matches per fragment.

## Requirements

### 1. Test: filter chips are buttons, not href-less anchors

```python
import re

def test_filter_chips_are_buttons_not_hrefless_anchors(client, project_factory):
    project = project_factory(...)
    response = client.get(
        f"/project/{project.id}/auto-merge/events?page=0&page_size=10"
    )
    html = response.text

    # No <a hx-get="...auto-merge/events..."> without href.
    bad = re.findall(
        r'<a\b(?![^>]*\bhref=)[^>]*\bhx-get="[^"]*/auto-merge/events[^"]*"[^>]*>',
        html,
    )
    assert bad == [], f"href-less <a hx-get> for filter chips remains:\n{bad}"

    # At least 7 filter chip buttons present.
    chip_buttons = re.findall(
        r'<button\b[^>]*\btype="button"[^>]*\bhx-get="[^"]*/auto-merge/events[^"]*"',
        html,
    )
    assert len(chip_buttons) >= 7, f"Expected ≥7 filter chip buttons; got {len(chip_buttons)}"
```

### 2. Test: `(view)` is a button in event rows

```python
def test_view_link_is_button_not_hrefless_anchor(client, project_factory, daemon_event_factory):
    project = project_factory(...)
    daemon_event_factory(project_id=project.id, event_type="step_launched", message="x")
    response = client.get(
        f"/project/{project.id}/auto-merge/events?page=0&page_size=10"
    )
    html = response.text

    # Each row's (view) action must be a <button>
    bad = re.findall(
        r'<a\b(?![^>]*\bhref=)[^>]*\bhx-get="[^"]*/auto-merge/events/\d+[^"]*"[^>]*>',
        html,
    )
    assert bad == []
    view_buttons = re.findall(
        r'<button\b[^>]*\btype="button"[^>]*\bhx-get="[^"]*/auto-merge/events/\d+"',
        html,
    )
    assert len(view_buttons) >= 1
```

### 3. Test: 7d/30d rollup toggles are buttons

```python
def test_rollup_window_toggles_are_buttons(client, project_factory):
    project = project_factory(...)
    response = client.get(f"/project/{project.id}/auto-merge/rollup?window=7d")
    html = response.text

    bad = re.findall(
        r'<a\b(?![^>]*\bhref=)[^>]*\bhx-get="[^"]*/auto-merge/rollup[^"]*"[^>]*>',
        html,
    )
    assert bad == []
    toggles = re.findall(
        r'<button\b[^>]*\btype="button"[^>]*\bhx-get="[^"]*/auto-merge/rollup[^"]*"',
        html,
    )
    # 7d and 30d
    assert len(toggles) == 2, f"Expected exactly 2 window toggles; got {len(toggles)}"
```

### 4. Test: pagination Prev/Next are buttons

```python
def test_pagination_links_are_buttons(client, project_factory, daemon_event_factory):
    project = project_factory(...)
    # Create enough events to trigger pagination
    for i in range(60):
        daemon_event_factory(project_id=project.id, event_type="auto_merge_health_probe", message=f"probe-{i}")
    response = client.get(
        f"/project/{project.id}/auto-merge/events?page=0&page_size=50"
    )
    html = response.text

    bad = re.findall(
        r'<a\b(?![^>]*\bhref=)[^>]*\bhx-get="[^"]*/auto-merge/events\?page=[^"]*"[^>]*>',
        html,
    )
    assert bad == []
    # 'Next' (page=1) should be a button.
    next_btn = re.search(
        r'<button\b[^>]*\btype="button"[^>]*\bhx-get="[^"]*page=1[^"]*"[^>]*>\s*Next\s*</button>',
        html,
    )
    assert next_btn, "Next pagination button not found"
```

### 5. Test placement

All four tests live under `tests/dashboard/` because they use the
`client` fixture (I-00067).

### 6. CSS class assertions

If any test asserts on CSS class names, use the attribute-scoped form
(I-00067):

```python
assert re.search(r'class\s*=\s*"[^"]*\bauto-merge-chip-btn\b[^"]*"', html)
```

## Project Conventions

`tests/CLAUDE.md`. No live DB; no `importlib.reload`.

## TDD Requirement

Coverage step — `tdd_red_evidence = "n/a — coverage step (tests-impl)"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Targeted only:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00094",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/dashboard/test_auto_merge_routes.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — coverage step (tests-impl)",
  "blockers": [],
  "notes": ""
}
```
