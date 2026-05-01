# I-00056: Code page lands on a wall of prose — components hidden, hard to scan

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-01
**Reported By**: sergio
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

The Code Understanding page (`/project/{id}/code`) opens with the architecture-map markdown body — eight H2 sections of LLM-generated prose, ~70 lines total — before the user sees the navigable component cards. Module discovery is buried below the fold; the page reads as a wall of text instead of an actionable index.

## Project Context

Read the project's `CLAUDE.md` (root) for architecture and hard rules. Sub-CLAUDE files relevant here:
- `dashboard/CLAUDE.md` — htmx, Tailwind prebuilt via `make css`, fragment template conventions.
- `orch/CLAUDE.md`, `orch/rag/CLAUDE.md` — mapgen pipeline.

## Browser Evidence

- `evidences/pre/I-00056-page-top-light.png` — Top of the Code page; user sees only the "Architecture Map" H1 + Purpose paragraph. Components cards and the standalone diagram are far below the visible viewport.
- DOM snapshot from investigation confirms 4 component cards exist at refs e234/e241/e248/e255 — but they sit *after* the entire architecture markdown body in render order.

## Steps to Reproduce

1. Visit any managed project's Code page after a successful code-map run, e.g. `http://iw-dev-01:9900/project/iw-ai-core/code`.
2. Observe the initial viewport.

**Expected**: The user lands on actionable navigation — at minimum a compact list of component names/paths reachable in one click — without having to read the architectural prose first.

**Actual**: The page opens at "Architecture Map" + "Purpose" prose. The user must scroll past 8 H2 sections (~70 lines of LLM text) to reach the component cards.

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/code"
playwright-cli snapshot
# After fix: expect a chip strip ABOVE the prose body.
playwright-cli evaluate "(()=>{ const chip = document.querySelector('#code-component-chips'); const prose = document.querySelector('.prose-doc'); if(!chip || !prose) return 'missing'; return chip.compareDocumentPosition(prose) & Node.DOCUMENT_POSITION_FOLLOWING ? 'chips-before-prose' : 'wrong-order' })()"
```

## Root Cause Analysis

Two cooperating issues:

1. **Layout** — `dashboard/templates/fragments/code_architecture_view.html:1-46` renders content in this order:
   - "ARCHITECTURE" header
   - The full architecture-map markdown (`{{ content_html | safe }}`)
   - Components cards (htmx-loaded into `#code-components-section`)
   - Architecture diagram (htmx-loaded fragment)
   The cards live AFTER the prose body, so the first thing the user sees is text, not navigation.

2. **Prose length** — `orch/rag/mapgen.py:49-67` `_GROUNDING_TEMPLATE` instructs the LLM to "Write 2–5 concise sentences (or a short bulleted list where natural)" per section. Combined with the 8 sections in `MapGenerator.QUESTIONS` (`orch/rag/mapgen.py:78`), that's 16–40 sentences of prose stacked at the top of the page. Even after I-00055 removes the inline diagram, the body remains visually heavy.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/templates/fragments/code_architecture_view.html` | Components cards rendered after prose; no compact chip surface above the fold |
| `dashboard/utils/markdown.py` | Renders all H2s as flat sections; no collapsible scaffold |
| `dashboard/routers/code.py` | No chip-strip endpoint (only the full cards endpoint) |
| `orch/rag/mapgen.py` | Prompt instructs 2–5 sentences per section, producing long prose |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | (a) Add `wrap_h2_sections_collapsible()` helper in `dashboard/utils/markdown.py` — wraps each H2 + its content in `<details>`, only the first H2 (typically `Purpose`) carries the `open` attribute. (b) Apply the helper inside `_render_architecture_html` (`dashboard/routers/code_ui.py`). (c) Add a new chip-strip endpoint in `dashboard/routers/code.py` returning `code_module_chips.html`. (d) Tighten `_GROUNDING_TEMPLATE` in `orch/rag/mapgen.py` from "2–5 concise sentences" to "1–3 concise sentences". | — |
| S02 | CodeReview (backend) | Review S01 | — |
| S03 | Frontend | (a) New fragment `dashboard/templates/fragments/code_module_chips.html` — single horizontal row of chips (name + path code) with `hx-get` to `/code/modules/{slug}` targeting `#code-detail-panel`. (b) Insert chip strip into `code_architecture_view.html` ABOVE the prose body (`<div class="prose-doc ...">`). (c) Run `make css`. | — |
| S04 | CodeReview (frontend) | Review S03 | — |
| S05 | Tests | (a) Unit test the wrap helper (Purpose `<details open>`, others `<details>` without `open`, body content preserved). (b) Endpoint test for `/api/projects/{id}/code/modules/chips`. (c) Dashboard test: chip strip element appears in DOM order before `.prose-doc`. (d) Mapgen prompt assertion: template now says "1–3 concise sentences". | — |
| S06 | CodeReview (tests) | Review S05 | — |
| S07 | CodeReview_Final | Cross-step review | — |
| S08..S12 | QV Gates | lint, format, typecheck, unit-tests, integration-tests | — |
| S13 | QV Browser | Chip strip renders above the prose; click a chip → module detail panel populates; non-Purpose H2s start collapsed; expanding works; no regression on cards section | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — content is regenerated by the existing `regen-map` job.

### Code Changes

- **Files to modify**: `dashboard/utils/markdown.py`, `dashboard/routers/code_ui.py`, `dashboard/routers/code.py`, `dashboard/templates/fragments/code_architecture_view.html`, `orch/rag/mapgen.py`
- **Files to add**: `dashboard/templates/fragments/code_module_chips.html`, `tests/unit/dashboard/test_collapsible_h2.py`, `tests/dashboard/test_code_module_chips.py`, `tests/unit/rag/test_mapgen_prompt.py`
- **Nature of change**: Rendering / layout / new compact navigation surface; one-line prompt edit.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00056_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00056_S01_Backend_prompt.md` | Prompt | S01 helper + endpoint + prompt tighten |
| `prompts/I-00056_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review |
| `prompts/I-00056_S03_Frontend_prompt.md` | Prompt | S03 chip strip + reorder |
| `prompts/I-00056_S04_CodeReview_Frontend_prompt.md` | Prompt | S04 review |
| `prompts/I-00056_S05_Tests_prompt.md` | Prompt | S05 tests |
| `prompts/I-00056_S06_CodeReview_Tests_prompt.md` | Prompt | S06 review |
| `prompts/I-00056_S07_CodeReview_Final_prompt.md` | Prompt | S07 cross-step review |
| `prompts/I-00056_S13_BrowserVerification_prompt.md` | Prompt | S13 browser verification |
| `evidences/pre/I-00056-page-top-light.png` | Evidence | Pre-fix top-of-page screenshot |

## Test to Reproduce

The reproduction lives in `tests/dashboard/test_code_module_chips.py`:

```python
def test_i00056_chip_strip_renders_before_prose_body(client, db):
    """RED until I-00056 lands. Chip strip element must precede the prose body
    in DOM order so the user lands on navigation, not on a wall of text."""
    project = make_project_with_arch_map(db)
    resp = client.get(f"/project/{project.id}/code")
    assert resp.status_code == 200

    html = resp.text
    chips_idx = html.find('id="code-component-chips"')
    prose_idx = html.find('class="prose-doc')
    assert chips_idx >= 0, "chip strip element missing"
    assert prose_idx >= 0, "prose body missing"
    assert chips_idx < prose_idx, "chip strip must appear before prose body"
```

A second reproduction in `tests/unit/dashboard/test_collapsible_h2.py`:

```python
def test_i00056_wrap_h2_only_purpose_open():
    html_in = "<h1>Title</h1>\n<h2>Purpose</h2>\n<p>p1</p>\n<h2>Components</h2>\n<p>p2</p>"
    out = wrap_h2_sections_collapsible(html_in)
    assert '<details open><summary>Purpose</summary>' in out
    assert '<details><summary>Components</summary>' in out
    assert '<details open><summary>Components</summary>' not in out
    assert '<p>p1</p>' in out and '<p>p2</p>' in out
```

## Acceptance Criteria

### AC1: Component chips render above the prose

```
Given the Code page is rendered for a project with a completed code-map
When the response HTML is inspected
Then the element with id "code-component-chips" appears before the element with class "prose-doc" in DOM order
```

### AC2: Chip click loads module detail in #code-detail-panel

```
Given the chip strip is visible
When the user clicks a chip
Then the corresponding module detail loads via htmx into #code-detail-panel and the panel scrolls into view
```

### AC3: Non-Purpose H2 sections start collapsed

```
Given the Code page is rendered
When the architecture-map markdown contains H2 sections "Purpose", "Components", "Entry Points", ...
Then "Purpose" renders as a <details open><summary>Purpose</summary>... block
And every other H2 renders as a <details><summary>...</summary>... block (no open attribute)
```

### AC4: Mapgen prompt asks for shorter sections

```
Given the next code-map run
When MapGenerator builds the grounding prompt for each H2 section
Then the prompt instructs the LLM to "Write 1–3 concise sentences (or a short bulleted list where natural)" — not 2–5
```

### AC5: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the chip-strip-before-prose dashboard test, the wrap-helper unit test, the chips endpoint test, and the mapgen prompt assertion all pass
```

## Regression Prevention

- DOM-order assertion guards against future template refactors that put cards/chips after prose again.
- Wrap-helper unit test pins the "Purpose-only-open" rule.
- Mapgen prompt-text assertion locks in the shorter-prose contract for future edits.

## Dependencies

- **Depends on**: None. Recommended (but not required) to ship after I-00055 so the architecture markdown is already de-duplicated when the chip strip is introduced — purely cosmetic ordering.
- **Blocks**: None.

## TDD Approach

- Reproducing tests: chip-strip-before-prose (dashboard), wrap-helper Purpose-only-open (unit).
- Unit tests: wrap helper edge cases (no H2 at all → unchanged; only one H2 → wrapped open; nested HTML inside body preserved).
- Endpoint test: chips fragment endpoint returns links to `/api/projects/{id}/code/modules/{slug}` for every parsed module.
- Mapgen prompt-text assertion: literal string match on the new "1–3 concise sentences" instruction.

## Notes

- We considered making H2 collapse state per-project localStorage. Decided against — stateless on every reload keeps the implementation tight and matches "land on navigation, not on prose" goal regardless of prior session state. Easy to add later if requested.
- The chips fragment reuses `parse_modules_from_level1` (same parser as the cards endpoint) so chip set and card set always match.
- Prompt edit is one line and safe; takes effect on the next code-map run for each project.
