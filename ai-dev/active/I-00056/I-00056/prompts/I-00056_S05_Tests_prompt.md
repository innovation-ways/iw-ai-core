# I-00056_S05_Tests_prompt

**Work Item**: I-00056 -- Code page lands on a wall of prose — components hidden, hard to scan
**Step**: S05
**Agent**: Tests

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Testcontainers via pytest fixtures allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `uv run iw item-status I-00056 --json`
- `ai-dev/active/I-00056/I-00056_Issue_Design.md`
- All implementation reports: `ai-dev/active/I-00056/reports/I-00056_S0{1,3}_*_report.md`
- `dashboard/utils/markdown.py` (helper added in S01)
- `dashboard/routers/code.py` (chips endpoint added in S01)
- `dashboard/routers/code_ui.py` (helper applied in S01)
- `dashboard/templates/fragments/code_module_chips.html` (created in S03)
- `dashboard/templates/fragments/code_architecture_view.html` (slot inserted in S03)
- `orch/rag/mapgen.py` (`_GROUNDING_TEMPLATE`)
- `tests/CLAUDE.md`, `tests/conftest.py`, `tests/dashboard/conftest.py`

## Output Files

- `ai-dev/active/I-00056/reports/I-00056_S05_Tests_report.md`
- `tests/unit/dashboard/test_collapsible_h2.py` (new)
- `tests/dashboard/test_code_module_chips.py` (new)
- `tests/unit/rag/test_mapgen_prompt.py` (new) — single-line assertion

## Context

You write the regression coverage for **I-00056**. Four arms:
(a) wrap helper unit tests, (b) chips endpoint test, (c) chips-slot-before-prose dashboard test, (d) mapgen prompt-text assertion.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Tests must verify **specific values**, not just shape:

- BAD: `assert "details" in html`
- GOOD: `assert '<details open><summary>Purpose</summary>' in html` and `assert '<details><summary>Components</summary>' in html`

For this incident specifically:

- BAD: `assert html.count("details") >= 2` — passes even if every `<details>` is open.
- GOOD: assert exactly one `<details open>` AND at least one `<details>` without `open`.
- BAD: `assert "code-component-chips-slot" in html` — passes regardless of position.
- GOOD: `assert html.find("code-component-chips-slot") < html.find('class="prose-doc')` — proves order.

## Requirements

### 1. Unit tests for `wrap_h2_sections_collapsible`

Create `tests/unit/dashboard/test_collapsible_h2.py`. Match the project's existing unit test pattern (look at `tests/unit/` for conventions; if a `dashboard/` subdirectory does not exist there, create it consistent with how `tests/dashboard/` is organised — match what `tests/CLAUDE.md` prescribes).

Cover:

```python
def test_purpose_h2_renders_open():
    html_in = "<h1>Title</h1><h2>Purpose</h2><p>p1</p>"
    out = wrap_h2_sections_collapsible(html_in)
    assert "<details open><summary>Purpose</summary>" in out
    assert "<p>p1</p>" in out


def test_subsequent_h2s_render_closed():
    html_in = "<h2>A</h2><p>a</p><h2>B</h2><p>b</p>"
    out = wrap_h2_sections_collapsible(html_in)
    assert "<details open><summary>A</summary>" in out
    assert "<details><summary>B</summary>" in out
    assert "<details open><summary>B</summary>" not in out


def test_pre_h1_content_left_at_top_level():
    html_in = "<h1>Title</h1><p>intro</p><h2>Purpose</h2><p>body</p>"
    out = wrap_h2_sections_collapsible(html_in)
    # The intro paragraph must NOT be inside a <details>
    assert "<p>intro</p>" in out
    purpose_idx = out.find("<details open>")
    assert out.find("<p>intro</p>") < purpose_idx


def test_no_h2_returns_input_unchanged():
    html_in = "<h1>X</h1><p>only paragraph</p>"
    assert wrap_h2_sections_collapsible(html_in) == html_in


def test_idempotent():
    html_in = "<h2>A</h2><p>a</p><h2>B</h2><p>b</p>"
    once = wrap_h2_sections_collapsible(html_in)
    twice = wrap_h2_sections_collapsible(once)
    assert once == twice


def test_body_html_preserved():
    html_in = '<h2>Components</h2><ul><li><strong>X</strong> (<code>x/</code>)</li></ul>'
    out = wrap_h2_sections_collapsible(html_in)
    assert "<ul><li><strong>X</strong> (<code>x/</code>)</li></ul>" in out
```

Adjust assertion strings if the implementation produces semantically equivalent but textually different output (e.g. `<details open="">` vs `<details open>`). The tests must reject the OLD behaviour but pass on the NEW; if you find the helper outputs `<details open="">`, change the assertion to match — do NOT change the helper to satisfy a string preference.

### 2. Chips endpoint test

In `tests/dashboard/test_code_module_chips.py`:

```python
def test_chips_endpoint_returns_one_link_per_module(client, db):
    project = make_project(db, "p")
    seed_project_doc(
        db,
        project_id=project.id,
        doc_id="architecture-map",
        doc_type="architecture",
        content=(
            "# Architecture Map\n## Components\n"
            "- **Daemon (`orch/daemon/`)**: x\n"
            "- **Dashboard (`dashboard/`)**: y\n"
        ),
    )
    seed_completed_code_index_job(db, project.id, doc_id="architecture-map")

    resp = client.get(f"/api/projects/{project.id}/code/modules/chips")
    assert resp.status_code == 200

    html = resp.text
    assert 'id="code-component-chips"' in html
    assert html.count("hx-target=\"#code-detail-panel\"") == 2
    assert "/code/modules/orch-daemon" in html
    assert "/code/modules/dashboard" in html
```

### 3. Chips slot precedes prose (page-level test)

Same file or a sibling, depending on conftest fixtures:

```python
def test_chips_slot_renders_before_prose_body(client, db):
    project = make_project_with_arch_map(db)  # any helper that ends with a code-map run
    resp = client.get(f"/project/{project.id}/code")
    assert resp.status_code == 200

    html = resp.text
    chips_idx = html.find('id="code-component-chips-slot"')
    prose_idx = html.find('class="prose-doc')
    assert chips_idx >= 0, "chip slot missing"
    assert prose_idx >= 0, "prose body missing"
    assert chips_idx < prose_idx, "chip slot must precede prose body"
```

### 4. Mapgen prompt-text assertion

In `tests/unit/rag/test_mapgen_prompt.py`:

```python
from orch.rag.mapgen import _GROUNDING_TEMPLATE

def test_grounding_template_asks_for_short_sections():
    """RED until I-00056 lands. Locks the rule at 1-3 sentences so future
    edits don't silently inflate prose length again."""
    text = _GROUNDING_TEMPLATE.template
    assert "1–3 concise sentences" in text
    assert "2–5 concise sentences" not in text
```

If the project's mapgen tests live in `tests/unit/rag/test_mapgen.py` and you'd rather extend that file (e.g. to share fixtures), do so — but keep the assertion semantically equivalent.

### 5. Run the full local gate

```bash
make test-unit
make test-integration   # if currently green on main; otherwise scope to changed paths
make lint && make typecheck
```

## Project Conventions

Read `tests/CLAUDE.md`. Critical rules:

- NEVER connect tests to the live DB (port 5433). Testcontainers only.
- Replace psycopg2 URLs with psycopg in testcontainers.
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- Don't mock the DB.

## Pre-flight Quality Gates

```bash
make format
make typecheck
make lint
```

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "Tests",
  "work_item": "I-00056",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/dashboard/test_collapsible_h2.py",
    "tests/dashboard/test_code_module_chips.py",
    "tests/unit/rag/test_mapgen_prompt.py"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
