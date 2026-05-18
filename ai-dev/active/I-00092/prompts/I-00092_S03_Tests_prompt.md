# I-00092_S03_Tests_prompt

**Work Item**: I-00092 — Auto-merge filter chip never highlights the active filter
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers in pytest fixtures only.

## ⛔ Migrations: agents generate, daemon applies

N/A.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00092 --json`.
- `ai-dev/active/I-00092/I-00092_Issue_Design.md` — MANDATORY read; the
  `Test to Reproduce`, `Acceptance Criteria`, and `TDD Approach`
  sections enumerate the tests you must write.
- `ai-dev/active/I-00092/reports/I-00092_S01_Frontend_report.md`
- `dashboard/templates/fragments/auto_merge_events_table.html` (post-S01)
- `tests/CLAUDE.md`
- `skills/iw-ai-core-testing/SKILL.md`
- `tests/dashboard/conftest.py` — `client` fixture

## Output Files

- `ai-dev/active/I-00092/reports/I-00092_S03_Tests_report.md`

## Context

S01 fixed the active-chip comparison so the URL's `type=…` parameter
controls which chip lights up. You write the regression tests.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE and passed even though the bug
was unfixed. Tests must verify SPECIFIC VALUES with attribute-scoped
matches:

- BAD: `assert "bg-primary" in html` (passes against the bug — the
  class is defined elsewhere in compiled CSS or the chip MIGHT have it)
- BAD: `assert "resolved" in html` (the word appears in event types)
- GOOD: scope to a single chip's `<a>` tag and check the `class`
  attribute carries `bg-primary` (or doesn't)
- GOOD: also assert `aria-pressed="true"` on the active chip

## Requirements

### 1. Helper for chip extraction

Write or extend a helper in `tests/dashboard/test_auto_merge_routes.py`
that returns each chip's `<a>` block keyed by its visible label:

```python
import re

def _extract_filter_chip_blocks(html: str) -> dict[str, str]:
    """Return {label: outer-<a>-tag-as-html} for each filter chip in the
    events-table fragment. Raises if not all 7 chips are found.
    """
    # The chips live inside <div class="flex flex-wrap gap-2">…</div>.
    # Each chip is an <a> whose body text is the label.
    pattern = re.compile(
        r'(<a\b[^>]*?>\s*([\w_]+)\s*</a>)',
        re.DOTALL,
    )
    out: dict[str, str] = {}
    for match in pattern.finditer(html):
        anchor, label = match.group(1), match.group(2)
        if 'hx-get=' in anchor and 'auto-merge/events' in anchor:
            out[label] = anchor
    expected = {"all", "resolved", "attempted", "failed",
                "skipped", "health_probe", "config_updated"}
    assert expected <= out.keys(), f"missing chips: {expected - out.keys()}"
    return out
```

### 2. Test: `resolved` filter is active

```python
def test_filter_chip_resolved_is_highlighted_when_active(client, project_factory):
    project = project_factory(...)
    response = client.get(
        f"/project/{project.id}/auto-merge/events"
        "?page=0&page_size=10&type=merge_auto_resolved"
    )
    assert response.status_code == 200
    chips = _extract_filter_chip_blocks(response.text)

    # Attribute-scoped check (I-00067): the class attribute on the
    # 'resolved' chip's <a> contains bg-primary.
    assert re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', chips["resolved"])
    assert 'aria-pressed="true"' in chips["resolved"]

    for other in ("all", "attempted", "failed", "skipped",
                  "health_probe", "config_updated"):
        assert 'bg-primary' not in chips[other], (
            f"'{other}' should NOT carry bg-primary when 'resolved' is active"
        )
        assert 'aria-pressed="false"' in chips[other]
```

### 3. Test: `all` is active when no `type` param

```python
def test_filter_chip_all_is_highlighted_when_no_type_param(client, project_factory):
    project = project_factory(...)
    response = client.get(
        f"/project/{project.id}/auto-merge/events?page=0&page_size=10"
    )
    chips = _extract_filter_chip_blocks(response.text)
    assert re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', chips["all"])
    assert 'aria-pressed="true"' in chips["all"]
    for other in ("resolved", "attempted", "failed", "skipped",
                  "health_probe", "config_updated"):
        assert 'bg-primary' not in chips[other]
```

### 4. Test: chip `title` matches the event_type

```python
def test_filter_chip_title_tooltips_match_event_types(client, project_factory):
    project = project_factory(...)
    response = client.get(
        f"/project/{project.id}/auto-merge/events?page=0&page_size=10"
    )
    chips = _extract_filter_chip_blocks(response.text)
    assert 'title="merge_auto_resolved"' in chips["resolved"]
    assert 'title="merge_auto_resolution_attempted"' in chips["attempted"]
    assert 'title="merge_auto_resolution_failed"' in chips["failed"]
    assert 'title="merge_auto_resolution_skipped"' in chips["skipped"]
    assert 'title="auto_merge_health_probe"' in chips["health_probe"]
    assert 'title="auto_merge_config_updated"' in chips["config_updated"]
    assert 'title="all event types"' in chips["all"]
```

### 5. Test placement

ALL these tests live under `tests/dashboard/` because they use the
`client` fixture (registered only in `tests/dashboard/conftest.py`).
Placing them under `tests/unit/` or `tests/integration/` fails with
`fixture 'client' not found` (I-00067).

### 6. CSS class assertions use the attribute-scoped form (I-00067)

```python
# BAD — substring can match inside <script>, data-attr, CSS comment
assert "bg-primary" in chips["resolved"]

# GOOD — anchored to the class attribute
assert re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', chips["resolved"])
```

## Project Conventions

- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`.
- Tests MUST NOT connect to the live DB (port 5433).
- No `importlib.reload(orch.config)`.

## TDD Requirement

These are coverage-step tests. Per the design template, your
`tdd_red_evidence` should read `n/a — coverage step (tests-impl)`. The
tests target the specific gap fixed by S01.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Targeted only:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

Do NOT run `make test-unit` or `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00092",
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
