# I-00056_S01_Backend_prompt

**Work Item**: I-00056 -- Code page lands on a wall of prose — components hidden, hard to scan
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Testcontainers via pytest fixtures allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp against the live DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00056 --json`.
- `ai-dev/active/I-00056/I-00056_Issue_Design.md`
- `dashboard/utils/markdown.py` — render_markdown lives here; new helper goes here
- `dashboard/routers/code_ui.py` — `_render_architecture_html` (apply helper here)
- `dashboard/routers/code.py` — existing `list_modules` returns cards; add a parallel `list_modules_chips`
- `dashboard/templates/fragments/code_module_cards.html` — reference for the existing card template (don't change it)
- `orch/rag/parser.py` — `parse_modules_from_level1` (reuse for chips endpoint)
- `orch/rag/mapgen.py` — `_GROUNDING_TEMPLATE` at lines 49-67

## Output Files

- `ai-dev/active/I-00056/reports/I-00056_S01_Backend_report.md`

## Context

Read the design document first, then `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/rag/CLAUDE.md`.

## Requirements

### 1. `wrap_h2_sections_collapsible` helper

In `dashboard/utils/markdown.py`, add a function:

```python
def wrap_h2_sections_collapsible(html: str) -> str:
    """Wrap each H2 (and the content following it up to the next H2 or end)
    in a <details> block with a <summary> derived from the H2 text.

    The FIRST H2 in document order is rendered with the `open` attribute.
    Subsequent H2s render closed by default. Text outside any H2 (e.g. the
    leading H1 + paragraph) is left untouched.

    Idempotent: running the helper twice is a no-op (the second pass detects
    that H2s are already inside a <details> and returns the input unchanged).
    """
```

Implementation notes:
- Use BeautifulSoup (already a dashboard dependency — `dashboard/utils/markdown.py` already imports it conditionally for callouts).
- Walk siblings until the next H2 or end-of-document; group them into the `<details>` body.
- The `<summary>` text is the H2's text content (no nested HTML promoted into the summary).
- Preserve any HTML inside the body verbatim (paragraphs, lists, code blocks, embedded `<pre data-lang="mermaid">` blocks if any survive I-00055's strip helper).
- Only `<h2>` elements at the top level of the parsed document trigger wrapping. Nested H2s inside callouts or blockquotes are out of scope.
- Idempotency check: if the parent of an H2 is already a `<summary>` or `<details>`, leave it alone.

### 2. Apply the helper in `_render_architecture_html`

In `dashboard/routers/code_ui.py:81-85`, after `render_markdown(processed)`, call the new helper:

```python
def _render_architecture_html(arch_doc: Any) -> str | None:
    if arch_doc is None or not arch_doc.content:
        return None
    cleaned = strip_trailing_arch_diagram_section(arch_doc.content)  # from I-00055
    processed = _preprocess_mermaid(cleaned)
    html = render_markdown(processed)
    return wrap_h2_sections_collapsible(html)
```

Import the new helper from `dashboard.utils.markdown`.

### 3. Chip-strip endpoint

In `dashboard/routers/code.py`, add:

```python
@router.get("/modules/chips", response_class=HTMLResponse)
async def list_modules_chips(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Return a compact horizontal strip of module chips — name + path code.

    Used at the top of the Code page so the user lands on navigation, not on
    the architecture-map prose. Same parser as list_modules; subset rendering.
    """
    _get_project_or_404(project_id, db)
    level1_doc = _get_level1_doc(project_id, db)

    if level1_doc is None:
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "fragments/code_empty_state.html",
            {"project_id": project_id},
            status_code=404,
        )

    modules = parse_modules_from_level1(level1_doc.content or "")

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/code_module_chips.html",
        {"modules": modules, "project_id": project_id},
    )
```

Place it next to `list_modules` (route `/modules`) so the related routes live together. The new fragment template is created in S03 — do not block S01 on it; the import path is `fragments/code_module_chips.html`. If the template doesn't yet exist when this endpoint is exercised manually, that's expected — the test in S05 covers it after S03 lands.

### 4. Tighten the mapgen grounding prompt

In `orch/rag/mapgen.py:63`, change the rule:

```
- Write 2–5 concise sentences (or a short bulleted list where natural).
```

to:

```
- Write 1–3 concise sentences (or a short bulleted list where natural).
```

This is a single-line edit. Do NOT touch other rules.

### 5. No other changes

Do NOT touch:

- `dashboard/templates/fragments/code_architecture_view.html` — that's S03's territory.
- `dashboard/templates/fragments/code_module_cards.html` — leave the existing cards as-is.
- `parse_modules_from_level1` — reuse, don't refactor.
- Any test file — that's S05's job.

## Project Conventions

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`, `orch/rag/CLAUDE.md`. Notable: routers thin (logic in helpers), Tailwind classes prebuilt, no new direct DB calls from helpers.

## TDD Requirement

1. **RED**: Note that without S01, no chip-strip endpoint, no collapsible helper, and the prompt still says 2–5. The S05 tests will codify these as RED expectations.
2. **GREEN**: Implement the four pieces above. Sanity-check by hitting the chips endpoint manually if a dev server is up.
3. **REFACTOR**: Tidy the helper docstrings; ensure typing is precise (`str -> str`, no `Any` leaks).

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

```bash
make format
make typecheck
make lint
```

## Test Verification

```bash
make test-unit
```

Must pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00056",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/utils/markdown.py",
    "dashboard/routers/code_ui.py",
    "dashboard/routers/code.py",
    "orch/rag/mapgen.py"
  ],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
