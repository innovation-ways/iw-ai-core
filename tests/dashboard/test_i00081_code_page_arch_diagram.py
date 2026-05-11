"""Regression + reproduction tests for I-00081.

Pre-fix bug: the Code-page Architecture Diagram widget showed
"Syntax error in text — mermaid version 11.14.0" whenever the stored
``diagram-architecture`` ProjectDoc was the **Markdown-with-fences** form
emitted by the ``iw-doc-generator`` skill (an `# H1` + HTML comments + N
``` ```mermaid``` ``` fences, each with a ``---\\nconfig:\\n  layout: elk\\n---``
front-matter). The router shoved the whole Markdown blob into a
``<div class="mermaid">`` element and the client-side Mermaid renderer
choked on the leading ``#`` / blockquotes / inner ELK front-matter.

Post-fix (S01 + S03): ``_render_arch_diagram()`` detects the two shapes
(Markdown-doc vs. bare-DSL) and renders each one through the correct path:

* **Markdown-doc** → strip HTML comments + leading H1 + per-fence ELK
  front-matter, run through ``_preprocess_mermaid`` + ``render_markdown``,
  result is a string of ``<pre data-lang="mermaid">`` blocks the client
  Mermaid runtime can render.
* **Bare-DSL** (mapgen output) → unchanged: strip the ``<!-- purpose: -->``
  comment + ELK front-matter, return the cleaned DSL string, template
  wraps it in a single ``<div class="mermaid">``.

These tests assert **specific values** (counts of renderable diagram
blocks, presence of diagram bodies, absence of raw-Markdown leakage)
rather than shape, per the assertion-strength rules in
``skills/iw-ai-core-testing/SKILL.md`` and ``tests/CLAUDE.md``.

Container: see the live-DB guard in ``tests/conftest.py`` — this file
uses the testcontainer-backed ``db_session`` / ``test_project`` fixtures
re-exported by ``tests/dashboard/conftest.py``. **Never** the live DB.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.code_ui import _render_arch_diagram
from orch.db.models import CodeIndexJob, DocType, EditorialCategory, Project, ProjectDoc

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

# Markdown-doc shape — the iw-doc-generator output that triggers I-00081.
# Three fenced ```mermaid blocks, each with its own ELK front-matter, plus
# the H1 + HTML comments + "Why" blockquotes that pre-fix leaked into the
# .mermaid container and broke client rendering.
_MD_ARCH_DIAGRAM = (
    "# Demo Project — Architecture Diagram\n\n"
    "<!-- generated: 2026-05-11 -->\n"
    "<!-- doc_job: deadbeef-0000-0000-0000-000000000000 -->\n\n"
    "> **Why this diagram?** Physical topology.\n\n"
    "```mermaid\n"
    "---\n"
    "config:\n"
    "  layout: elk\n"
    "---\n"
    "flowchart TB\n"
    '    DB[("PostgreSQL")]\n'
    '    App["App"]\n'
    "    DB --> App\n"
    "```\n\n"
    "---\n\n"
    "> **Why this diagram?** Work-item lifecycle.\n\n"
    "```mermaid\n"
    "---\n"
    "config:\n"
    "  layout: elk\n"
    "---\n"
    "stateDiagram-v2\n"
    "    [*] --> Draft\n"
    "    Draft --> Active\n"
    "    Active --> Done\n"
    "```\n\n"
    "---\n\n"
    "> **Why this diagram?** Data model.\n\n"
    "```mermaid\n"
    "---\n"
    "config:\n"
    "  layout: elk\n"
    "---\n"
    "erDiagram\n"
    '    PROJECTS ||--o{ WORK_ITEMS : ""\n'
    "```\n"
)

# Bare-DSL shape — the orch/rag/mapgen.py output. Intentionally free of
# ``` ```mermaid``` ``` fences so ``html.count('<pre data-lang="mermaid">')``
# is an unambiguous signal of "Markdown-path was taken".
_BARE_DSL = (
    "<!-- purpose: shows overall architecture -->\n"
    "---\n"
    "config:\n"
    "  layout: elk\n"
    "---\n"
    "graph TD\n"
    "  A[CLI] --> B[Daemon]\n"
    "  B --> C[DB]\n"
)

# Architecture-map content kept deliberately free of any ``` ```mermaid``` ```
# fence — keeps the page-level ``<pre data-lang="mermaid">`` count attributable
# to the diagram doc only.
_ARCH_MAP_CONTENT = (
    "# Architecture Map\n\n"
    "## Purpose\nTest project for I-00081.\n\n"
    "## Components\n- **CLI**: command interface\n"
)


# ---------------------------------------------------------------------------
# Fixtures + helpers (mirror tests/dashboard/test_code_page_arch_diagram.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """TestClient with ``get_db`` overridden to the testcontainer ``db_session``.

    Pops ``IW_CORE_EXPECTED_INSTANCE_ID`` so the app's identity probe doesn't
    refuse to boot against the testcontainer.
    """
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    app = create_app()
    try:

        def override_get_db() -> Session:
            return db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


def _seed_arch_map(db_session: Session, project_id: str) -> str:
    """Seed the architecture-map doc — required for the Code page to enter
    the "has a completed job" branch on both routes."""
    doc = ProjectDoc(
        id=f"{project_id}:architecture-map",
        project_id=project_id,
        doc_id="architecture-map",
        title="Test Project — Architecture Map",
        slug="architecture-map",
        doc_type=DocType.architecture,
        tier="fully_automated",
        editorial_category=EditorialCategory.technical,
        status="published",
        content=_ARCH_MAP_CONTENT,
        generated_by="code-understanding:level1",
        source_paths=["*"],
    )
    db_session.add(doc)
    db_session.flush()
    return doc.id


def _seed_diagram_doc(
    db_session: Session, project_id: str, content: str, *, generated_by: str
) -> None:
    doc = ProjectDoc(
        id=f"{project_id}:diagram-architecture",
        project_id=project_id,
        doc_id="diagram-architecture",
        title="Demo Project — Architecture Diagram",
        slug="diagram-architecture",
        doc_type=DocType.diagram,
        tier="fully_automated",
        editorial_category=EditorialCategory.technical,
        status="published",
        content=content,
        generated_by=generated_by,
        source_paths=["*"],
    )
    db_session.add(doc)
    db_session.flush()


def _seed_completed_job(db_session: Session, project_id: str, arch_map_doc_id: str) -> None:
    job = CodeIndexJob(
        project_id=project_id,
        status="completed",
        provider="local",
        llm_model="gemma4:e4b",
        embed_model="qwen3-embedding:8b",
        index_tier="balanced",
        files_discovered=10,
        files_indexed=8,
        chunks_created=25,
        languages_detected=["python"],
        errors=[],
        doc_id=arch_map_doc_id,
        completed_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(job)
    db_session.flush()


def _extract_diagram_region(html: str) -> str:
    """Slice the Architecture-Diagram widget region out of the full page.

    The fragment renders ``<div id="code-arch-diagram" …> … </div><script>…``,
    so we slice from the ``id="code-arch-diagram"`` attribute up to the first
    ``</script>`` after it — that boundary cleanly covers the widget and the
    upgrade script body without bleeding into unrelated page content (e.g.
    the arch-map's own ``<h1>`` rendered above the widget).
    """
    start = html.index('id="code-arch-diagram"')
    end = html.index("</script>", start)
    return html[start:end]


# ---------------------------------------------------------------------------
# Test 1 — REPRODUCTION: Markdown-doc form renders as diagrams, not raw Markdown
# ---------------------------------------------------------------------------


def test_i00081_markdown_format_diagram_doc_renders_diagrams_not_raw_markdown(
    client: TestClient, db_session: Session, test_project: Project
) -> None:
    """Markdown-format ``diagram-architecture`` doc must render as
    ``<pre data-lang="mermaid">`` blocks (client-renderable), not as raw
    Markdown inside a ``<div class="mermaid">`` (which throws "Syntax error
    in text — mermaid version 11.14.0" client-side).

    Pre-fix server-side symptom: the whole Markdown blob (including ``# H1``,
    blockquotes, and literal ``` ```mermaid``` ``` fence strings) ended up
    inside a ``<div class="mermaid">`` element. Post-fix: that path is gone
    for the Markdown-doc shape; each fence becomes a ``<pre data-lang="mermaid">``
    block; the ELK front-matter is stripped before client render.
    """
    arch_map_id = _seed_arch_map(db_session, test_project.id)
    _seed_diagram_doc(
        db_session,
        test_project.id,
        _MD_ARCH_DIAGRAM,
        generated_by="skill:iw-doc-generator",
    )
    _seed_completed_job(db_session, test_project.id, arch_map_id)
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/code")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    html = resp.text

    # --- PRESENCE of the fix marker ----------------------------------------
    # 3 fenced blocks in the seed → expect 3 ``<pre data-lang="mermaid">`` blocks.
    # The arch-map content has no fences, so the count is attributable to the
    # diagram doc alone. ``>= 2`` is the contract from the design doc.
    pre_count = html.count('<pre data-lang="mermaid">')
    assert pre_count >= 2, (
        f"Expected >= 2 <pre data-lang='mermaid'> blocks for a 3-fence Markdown doc, "
        f"found {pre_count}. Pre-fix value is 0 (the whole blob was placed in a "
        f'<div class="mermaid">).'
    )

    # --- Diagram bodies survived ELK stripping ------------------------------
    assert "flowchart TB" in html, "flowchart TB diagram body missing"
    assert "stateDiagram-v2" in html, "stateDiagram-v2 diagram body missing"
    assert "erDiagram" in html, "erDiagram diagram body missing"

    # --- ABSENCE of the bug marker -----------------------------------------
    # No ``<div class="mermaid">`` should appear at all in the Markdown-doc
    # path — only the bare-DSL path produces those. (Page-wide assertion is
    # safe because the arch-map render uses ``<pre data-lang="mermaid">``,
    # never ``<div class="mermaid">``.)
    assert '<div class="mermaid">' not in html, (
        'Pre-fix bug: the whole Markdown blob ended up inside <div class="mermaid">. '
        'Post-fix: the Markdown-doc path must never produce <div class="mermaid">.'
    )

    # Defensive: even if a stray .mermaid div ever appears in the future,
    # the literal raw-Markdown fence string must NOT be inside one.
    assert '<div class="mermaid">```' not in html, "Literal fence leaked into .mermaid"
    assert '<div class="mermaid"># ' not in html, "Leading H1 leaked into .mermaid"
    assert '<div class="mermaid">> ' not in html, "Blockquote leaked into .mermaid"

    # --- ELK front-matter stripped before client render --------------------
    # mermaid.js in the dashboard has no ELK layout loader registered;
    # ``layout: elk`` reaching the client makes mermaid.render() throw.
    assert "layout: elk" not in html, (
        "'layout: elk' must be stripped from every fenced block before "
        "the client renderer sees it (else mermaid.render() throws)."
    )


# ---------------------------------------------------------------------------
# Test 2 — REGRESSION: bare-DSL form still renders as a single <div class="mermaid">
# ---------------------------------------------------------------------------


def test_i00081_bare_dsl_format_still_renders_single_mermaid_div(
    client: TestClient, db_session: Session, test_project: Project
) -> None:
    """The legacy bare-DSL form (``orch/rag/mapgen.py`` output) must still
    render via the existing ``<div class="mermaid">`` path with the
    ``<!-- purpose: -->`` value pulled out as the italic purpose line above
    the diagram. This test is the guard that I-00081's fix didn't break the
    happy path.
    """
    arch_map_id = _seed_arch_map(db_session, test_project.id)
    _seed_diagram_doc(
        db_session,
        test_project.id,
        _BARE_DSL,
        generated_by="code-understanding:mapgen",
    )
    _seed_completed_job(db_session, test_project.id, arch_map_id)
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/code")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    html = resp.text

    # Exactly ONE <div class="mermaid"> — proves the bare-DSL template branch
    # ran (not the Markdown-doc branch) AND that the legacy ``<div class="mermaid">``
    # element is intact.
    div_count = html.count('<div class="mermaid">')
    assert div_count == 1, (
        f"Expected exactly 1 <div class='mermaid'> for the bare-DSL path, "
        f"found {div_count}. The bare-DSL template branch must produce the "
        f"single legacy diagram container."
    )

    # No ``<pre data-lang="mermaid">`` should be attributable to the diagram
    # doc on the bare-DSL path. The arch-map content in this test is fence-free,
    # so an unambiguous zero-count assertion is safe here.
    pre_count = html.count('<pre data-lang="mermaid">')
    assert pre_count == 0, (
        f"Bare-DSL path must not produce <pre data-lang='mermaid'>; found {pre_count}. "
        "(Test isolates this by keeping the arch-map content fence-free.)"
    )

    # The DSL body survived (the ``<div>`` wraps the cleaned DSL).
    assert "graph TD" in html, "graph TD body missing from rendered DSL"
    assert "A[CLI]" in html, "A[CLI] node missing from rendered DSL"

    # The purpose line is rendered above the diagram.
    assert "shows overall architecture" in html, "purpose line not rendered"

    # The raw purpose comment must NOT survive in the page — it's pulled out
    # and rendered as text, not echoed as an HTML comment.
    assert "<!-- purpose:" not in html, "raw <!-- purpose: --> leaked to HTML"

    # The leading ``---\\nconfig:\\n  layout: elk\\n---`` front-matter from
    # the bare-DSL form must be stripped before the DSL is wrapped.
    assert "layout: elk" not in html, "ELK front-matter leaked into bare-DSL render"


# ---------------------------------------------------------------------------
# Test 3 — EDGE CASE: leading H1 from the Markdown doc is not duplicated
# ---------------------------------------------------------------------------


def test_i00081_markdown_doc_leading_h1_not_duplicated(
    client: TestClient, db_session: Session, test_project: Project
) -> None:
    """The diagram widget fragment has its own ``<h3>Architecture Diagram</h3>``
    title. The Markdown-doc form's leading ``# Demo Project — Architecture
    Diagram`` H1 is *also* a title — rendering both would give the user two
    "Architecture Diagram" headings stacked on top of each other.

    Post-fix: S01 strips a single leading ``# …`` H1 line before rendering,
    so no ``<h1>`` element appears inside the ``#code-arch-diagram`` region
    and the doc's H1 text is not echoed there.
    """
    arch_map_id = _seed_arch_map(db_session, test_project.id)
    _seed_diagram_doc(
        db_session,
        test_project.id,
        _MD_ARCH_DIAGRAM,
        generated_by="skill:iw-doc-generator",
    )
    _seed_completed_job(db_session, test_project.id, arch_map_id)
    db_session.commit()

    html = client.get(f"/project/{test_project.id}/code").text
    region = _extract_diagram_region(html)

    # The fragment's own static H3 must still be present.
    assert ">Architecture Diagram</h3>" in region, (
        "fragment's static <h3>Architecture Diagram</h3> missing from the widget"
    )

    # No <h1> inside the widget region — the doc's H1 was stripped.
    assert "<h1" not in region, (
        "Doc's leading H1 must be stripped before rendering — no <h1> may appear "
        "inside the #code-arch-diagram widget region."
    )

    # The doc's H1 *text* must not be echoed inside the widget either
    # (catches the case where a future change converts it to <h2> instead of
    # dropping it).
    assert "Demo Project — Architecture Diagram" not in region, (
        "Doc's H1 text must not be rendered inside the diagram widget — it duplicates "
        "the fragment's own 'Architecture Diagram' title."
    )


# ---------------------------------------------------------------------------
# Test 4 — htmx fragment route handles the Markdown-doc form
# ---------------------------------------------------------------------------


def test_i00081_api_code_architecture_endpoint_handles_markdown_doc(
    client: TestClient, db_session: Session, test_project: Project
) -> None:
    """``GET /project/{id}/api/code/architecture`` (the htmx fragment route)
    shares the same helper as the page route. It must also render the
    Markdown-doc form as ``<pre data-lang="mermaid">`` blocks without leaking
    raw Markdown into a ``.mermaid`` container.

    Note: this route returns the empty-state fragment if the
    ``architecture-map`` doc is missing — must seed it.
    """
    _seed_arch_map(db_session, test_project.id)
    _seed_diagram_doc(
        db_session,
        test_project.id,
        _MD_ARCH_DIAGRAM,
        generated_by="skill:iw-doc-generator",
    )
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/api/code/architecture")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    html = resp.text

    # Same fix-marker / bug-marker contract as the page-route test.
    pre_count = html.count('<pre data-lang="mermaid">')
    assert pre_count >= 2, (
        f"htmx fragment must render >= 2 <pre data-lang='mermaid'> blocks for a "
        f"3-fence Markdown doc, found {pre_count}."
    )
    assert "flowchart TB" in html, "flowchart TB diagram body missing from htmx fragment"
    assert "erDiagram" in html, "erDiagram diagram body missing from htmx fragment"

    # No raw-Markdown leak into a .mermaid container.
    assert '<div class="mermaid">' not in html, (
        "htmx fragment must not produce <div class='mermaid'> for the Markdown-doc form"
    )

    # ELK front-matter stripped before client render.
    assert "layout: elk" not in html, "'layout: elk' leaked through htmx fragment"


# ---------------------------------------------------------------------------
# Test 5 — Unit-ish: _render_arch_diagram detects the two formats correctly
# ---------------------------------------------------------------------------


def test_i00081_render_arch_diagram_helper_detects_format() -> None:
    """``_render_arch_diagram()`` is the format-detection helper introduced
    by S01. Direct-unit coverage of both branches is cheaper and faster than
    route tests for catching detection-logic regressions.

    Contract (per S01 report):
      * Markdown-doc form → ``(rendered_html, None, None)`` where
        ``rendered_html`` contains ``<pre data-lang="mermaid">`` blocks and
        no ``layout: elk``.
      * Bare-DSL form    → ``(None, cleaned_dsl, purpose)`` where
        ``cleaned_dsl`` has the front-matter + purpose comment stripped.
    """
    # ---- Markdown-doc branch -------------------------------------------------
    arch_html, arch_dsl, arch_purpose = _render_arch_diagram(_MD_ARCH_DIAGRAM)

    assert arch_html is not None, "Markdown-doc form must return non-None HTML"
    assert arch_dsl is None, f"Markdown-doc form must return dsl=None, got {arch_dsl!r}"
    assert arch_purpose is None, (
        f"Markdown-doc form must return purpose=None (purpose is inline in blockquotes), "
        f"got {arch_purpose!r}"
    )

    pre_count = arch_html.count('<pre data-lang="mermaid">')
    assert pre_count >= 2, (
        f"Markdown-doc form must render >= 2 <pre data-lang='mermaid'> blocks, found {pre_count}."
    )
    assert "flowchart TB" in arch_html
    assert "stateDiagram-v2" in arch_html
    assert "erDiagram" in arch_html
    assert "layout: elk" not in arch_html, (
        "ELK front-matter must be stripped from every fence body before render"
    )
    assert "<h1>" not in arch_html, (
        "Leading # H1 must be dropped before render (else duplicates the widget title)"
    )
    assert "<h1 " not in arch_html, (
        "Leading # H1 must be dropped before render (even with attributes)"
    )

    # ---- Bare-DSL branch -----------------------------------------------------
    arch_html, arch_dsl, arch_purpose = _render_arch_diagram(_BARE_DSL)

    assert arch_html is None, f"Bare-DSL form must return html=None, got {arch_html!r}"
    assert arch_dsl is not None, "Bare-DSL form must return non-None dsl"
    assert arch_purpose == "shows overall architecture", (
        f"Bare-DSL form must extract purpose from <!-- purpose: ... --> comment, "
        f"got {arch_purpose!r}"
    )
    assert "graph TD" in arch_dsl, "DSL body missing"
    assert "A[CLI]" in arch_dsl, "DSL nodes missing"
    assert "<!-- purpose:" not in arch_dsl, "purpose comment must be stripped from dsl"
    assert "layout: elk" not in arch_dsl, "ELK front-matter must be stripped from dsl"
