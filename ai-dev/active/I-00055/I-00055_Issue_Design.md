# I-00055: Architecture Diagram renders twice on Code page; inline copy unreadable in dark mode

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

The Code Understanding page (`/project/{id}/code`) renders the architecture mermaid diagram twice — once embedded inside the architecture-map markdown body and a second time below it from the standalone `diagram-architecture` ProjectDoc. In dark mode the inline copy is hard to read because its preserved YAML frontmatter (`config: layout: elk`) overrides the dashboard's mermaid theme initialization, while the bottom copy renders cleanly because that frontmatter is stripped on the way out.

## Project Context

Read the project's `CLAUDE.md` (root) for architecture and hard rules. Relevant sub-CLAUDE files:
- `dashboard/CLAUDE.md` — dashboard router & template patterns; htmx; Tailwind pre-build via `make css`.
- `orch/CLAUDE.md` — orch package structure.
- `orch/rag/CLAUDE.md` — Code Understanding pipeline (mapgen, ProjectDoc storage).

## Browser Evidence

- `evidences/pre/I-00055-bug-evidence-light.png` — Code page in light mode showing the start of the architecture-map markdown (top of two-diagram region).
- `evidences/pre/I-00055-dark-bottom-diagram.png` — Same page in dark mode at the same scroll position; demonstrates that the page fits two diagrams.
- DOM accessibility snapshot taken at investigation time confirmed two `document` (mermaid) regions present per page render — one embedded inside the architecture-map prose (refs e186/e192/e199…) and a separate one below the components cards (refs e268/e274/e281…).

## Steps to Reproduce

1. Visit any managed project's Code page, e.g. `http://iw-dev-01:9900/project/iw-ai-core/code`.
2. Click `Generate Code Map → Generate Code Map` (full index) and wait for the job to complete, or open a project that already has a recent code-map run.
3. Scroll through the Architecture panel from top to bottom.

**Expected**: Exactly one rendered architecture diagram, readable in both light and dark themes.

**Actual**: Two rendered architecture diagrams — one embedded mid-content under the `## Architecture Diagram` H2 inside the architecture-map prose, and a second one rendered below the components cards. In dark mode the embedded copy has poor text contrast; the bottom copy is readable.

## Browser Verification Script

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/code"
playwright-cli snapshot
# Count mermaid containers — expect exactly one after the fix.
playwright-cli evaluate "(()=>{ const m=document.querySelectorAll('div.mermaid, pre[data-lang=\"mermaid\"]'); return m.length })()"
# Toggle theme and assert the same count + that no diagram has invisible text.
```

## Root Cause Analysis

`MapGenerator._assemble_markdown()` at `orch/rag/mapgen.py:342-357` always appends a trailing `## Architecture Diagram` section to the architecture-map markdown content. That section contains:
- `<!-- purpose: ... -->` HTML comment
- A ` ```mermaid ` fenced block including `---\nconfig:\n  layout: elk\n---` YAML frontmatter

Mapgen ALSO stores the same diagram as a separate `diagram-architecture` ProjectDoc (see `orch/rag/mapgen.py:201-221`). The dashboard's Code page renders BOTH copies:

- `dashboard/routers/code_ui.py:144-153` loads the architecture-map AND the diagram-architecture docs and passes both into the template.
- `dashboard/templates/fragments/code_architecture_view.html:26` renders the architecture-map markdown via `{{ content_html | safe }}`. Markdown is preprocessed by `_preprocess_mermaid()` at `dashboard/routers/code_ui.py:76-78`, which converts the inline ` ```mermaid ` fence into `<pre data-lang="mermaid"><code>…</code></pre>` — *with the YAML frontmatter preserved verbatim*.
- `dashboard/templates/fragments/code_architecture_view.html:43-45` then includes `code_architecture_diagram.html`, which renders the standalone `diagram-architecture` doc inside `<div class="mermaid">…</div>`. Before this render the DSL is sanitised by `_clean_diagram_dsl()` at `dashboard/routers/code_ui.py:34-46`, which strips both the HTML comment and the YAML frontmatter.

Dark-mode readability difference: the bottom (clean) copy goes to Mermaid with no frontmatter, so the dashboard's theme init (set by `dashboard/static/vendor/mermaid/...` initialization in `components/libs/mermaid.html`) takes effect. The inline copy keeps its frontmatter, which appears to suppress the theme override and falls back to Mermaid defaults that don't contrast against the dark background.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/rag/mapgen.py` (mapgen content writer) | Always emits the duplicate diagram block into architecture-map content |
| `dashboard/routers/code_ui.py` (`_render_architecture_html`) | Renders the duplicate as-is; no de-duplication step |
| `dashboard/templates/fragments/code_architecture_view.html` | Combines markdown body + standalone diagram, producing two on-page mermaid containers |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Stop emitting the trailing `## Architecture Diagram` block in `_assemble_markdown`; add a small `strip_trailing_arch_diagram_section()` helper and call it from `_render_architecture_html` so legacy stored docs render once until regeneration | — |
| S02 | CodeReview (backend) | Review S01: correctness of the strip helper (idempotent, conservative — only matches a trailing H2 with the exact title), no regression for docs that lack the section | — |
| S03 | Tests | (a) `tests/unit/rag/test_mapgen.py`: assert `_assemble_markdown` output has no `## Architecture Diagram`, no `<!-- purpose:`, no ` ```mermaid `. (b) Unit test for the strip helper — legacy markdown blob in / clean prefix out, plus negative test (no trailing section → unchanged). (c) Dashboard test: project seeded with both docs, GET `/project/{id}/code`, assert exactly one mermaid container in the response. | — |
| S04 | CodeReview (tests) | Review S03: semantic correctness, falsifiability, regression coverage of the strip helper | — |
| S05 | CodeReview_Final | Cross-step review — mapgen change + render-time guard + tests compose into a complete fix | — |
| S06..S10 | QV Gates | lint, format, typecheck, unit-tests, integration-tests | — |
| S11 | QV Browser | After regen, hit the Code page in both themes; assert exactly one mermaid container; assert text in the diagram is visible against the page background | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — content is regenerated by the existing `regen-map` job, no schema change.

### Code Changes

- **Files to modify**: `orch/rag/mapgen.py`, `dashboard/routers/code_ui.py`
- **Nature of change**: Remove diagram emission from `_assemble_markdown`; add and apply a defensive strip helper at render time; add tests.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00055_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00055_S01_Backend_prompt.md` | Prompt | S01 fix instructions |
| `prompts/I-00055_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review |
| `prompts/I-00055_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00055_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of tests |
| `prompts/I-00055_S05_CodeReview_Final_prompt.md` | Prompt | S05 final cross-step review |
| `prompts/I-00055_S11_BrowserVerification_prompt.md` | Prompt | S11 browser verification |
| `evidences/pre/I-00055-bug-evidence-light.png` | Evidence | Pre-fix screenshot, light theme |
| `evidences/pre/I-00055-dark-bottom-diagram.png` | Evidence | Pre-fix screenshot, dark theme |

## Test to Reproduce

The reproduction lives in `tests/dashboard/test_code_page_arch_diagram.py`:

```python
def test_i00055_code_page_renders_architecture_diagram_exactly_once(client, db):
    """RED until I-00055 lands. Seeds an architecture-map doc whose markdown
    embeds a mermaid block (legacy shape) AND a standalone diagram-architecture
    doc, then asserts the rendered Code page contains exactly one mermaid
    container — proving both the mapgen content fix AND the render-time strip
    helper work end-to-end."""
    project = make_project(db, "p")
    seed_project_doc(
        db,
        project_id=project.id,
        doc_id="architecture-map",
        slug="architecture-map",
        doc_type="architecture",
        content=(
            "# Architecture Map\n\n## Purpose\nA test project.\n\n"
            "## Architecture Diagram\n\n"
            "<!-- purpose: example -->\n\n"
            "```mermaid\n---\nconfig:\n  layout: elk\n---\n"
            "graph TD\n  A --> B\n```\n"
        ),
    )
    seed_project_doc(
        db,
        project_id=project.id,
        doc_id="diagram-architecture",
        slug="diagram-architecture",
        doc_type="diagram",
        content="<!-- purpose: example -->\n---\nconfig:\n  layout: elk\n---\ngraph TD\n  A --> B",
    )
    seed_completed_code_index_job(db, project.id, doc_id="architecture-map")

    resp = client.get(f"/project/{project.id}/code")
    assert resp.status_code == 200

    html = resp.text
    inline = html.count('<pre data-lang="mermaid"')
    bottom = html.count('<div class="mermaid"')
    assert inline + bottom == 1, (
        f"expected exactly one mermaid container, got inline={inline} + bottom={bottom}"
    )
```

A second reproduction in `tests/unit/rag/test_mapgen.py`:

```python
def test_i00055_assemble_markdown_does_not_embed_diagram():
    g = MapGenerator(...)
    md = g._assemble_markdown(answers, mermaid="graph TD\n A-->B", purpose="x")
    assert "## Architecture Diagram" not in md
    assert "<!-- purpose:" not in md
    assert "```mermaid" not in md
```

## Acceptance Criteria

### AC1: Bug is fixed (mapgen)

```
Given a fresh code-map run
When MapGenerator._assemble_markdown produces the architecture-map content
Then the output contains no "## Architecture Diagram" H2, no "<!-- purpose:" comment, and no ```mermaid``` fence
```

### AC2: Bug is fixed (render-time guard)

```
Given a legacy architecture-map ProjectDoc whose content still contains a trailing "## Architecture Diagram" + mermaid block
When the Code page is rendered for that project
Then the response HTML contains exactly one mermaid container (sum of <pre data-lang="mermaid"> and <div class="mermaid"> equals 1)
```

### AC3: Dark mode is readable

```
Given the Code page is rendered in dark mode
When the user views the architecture diagram
Then all node text is legible against the diagram and page backgrounds (no dark-on-dark or near-zero-contrast text)
```

### AC4: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the unit test (mapgen) and the dashboard reproduction test pass
```

## Regression Prevention

- Unit assertion on `_assemble_markdown` keeps the diagram from sneaking back into architecture-map content.
- Dashboard test asserts exactly one mermaid container on the rendered page; protects against future regressions where another component starts re-emitting the diagram.
- Strip helper is unit-tested for both legacy-trailing-section and no-trailing-section inputs (idempotency).

## Dependencies

- **Depends on**: None
- **Blocks**: None (Incident B and Incident C are independent.)

## TDD Approach

- Reproducing test: dashboard test counting mermaid containers (fails before fix because legacy content double-renders).
- Unit tests: `_assemble_markdown` no longer emits the diagram; strip helper handles both shapes.
- Integration tests: existing mapgen / code page tests must continue to pass.

## Operational Follow-up (post-merge)

After merge, queue a code-map regeneration for every registered project so all stored architecture-map docs are refreshed without the inline diagram. This is operator work, not part of the fix itself:

```bash
# For each project_id from projects.toml or `iw projects list`:
curl -fsS -X POST "$DASHBOARD_URL/project/$pid/api/code/regen-map"
```

The defensive strip helper makes this non-urgent — pages will render correctly in the meantime.

## Notes

- We considered moving the diagram into a separate H2 in the markdown that the renderer always strips, but the cleaner path is "diagram-architecture is the canonical home; architecture-map is prose only".
- We considered re-rendering the inline mermaid through `_clean_diagram_dsl` instead of stripping the section. Rejected: it solves dark-mode readability but not the duplication.
- The strip helper is intentionally conservative (matches only a trailing `## Architecture Diagram` H2 followed by the rest of the document) so it cannot accidentally remove legitimate content from non-mapgen-authored docs.
