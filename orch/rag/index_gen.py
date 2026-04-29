"""Index page generation for code-understanding projects.

After a CodeIndexJob completes, generates (or updates) a `code-index` ProjectDoc
listing all available documentation grouped by doc_type.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import DocTier, DocType, EditorialCategory, Project, ProjectDoc
from orch.doc_service import DocService

logger = logging.getLogger(__name__)


def _extract_first_sentence(content: str | None) -> str:
    """Extract the first non-empty sentence from content.

    Strips markdown headers and finds the first sentence-ending punctuation.
    Returns '—' if content is None or no sentence found.
    """
    if not content:
        return "—"

    paragraphs = re.split(r"\n{2,}", content.strip())

    for para in paragraphs:
        stripped = re.sub(r"^#{1,6}\s+", "", para).strip()
        if not stripped:
            continue

        match = re.search(r"[^.!?]*[.!?]", stripped)
        if match:
            return match.group(0).strip()

    first_para = paragraphs[0] if paragraphs else ""
    stripped = re.sub(r"^#{1,6}\s+", "", first_para).strip()
    if stripped:
        return stripped[:80].strip() + ("…" if len(stripped) > 80 else "")

    return "—"


def _build_index_content(
    project_display_name: str,
    docs_by_type: dict[DocType, list[ProjectDoc]],
) -> str:
    """Build the markdown index page content."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    lines = [
        f"# Documentation Index — {project_display_name}",
        "",
        f"<!-- generated: {today} -->",
        "",
        (
            "> [!NOTE]\n"
            "> This index is auto-generated. "
            "Click a document to view its full content in the Docs section."
        ),
        "",
    ]

    arch_docs = docs_by_type.get(DocType.architecture, [])
    diagram_docs = docs_by_type.get(DocType.diagram, [])

    if arch_docs or diagram_docs:
        lines.append("## Architecture")
        lines.append("")
        lines.append("| Document | Description |")
        lines.append("|----------|-------------|")

        if arch_docs:
            for doc in arch_docs:
                if doc.doc_id == "architecture-map":
                    desc = _extract_first_sentence(doc.content)
                    lines.append(f"| [Architecture Overview](code-map) | {desc} |")

        for doc in diagram_docs:
            if doc.doc_id == "diagram-architecture":
                purpose_match = re.search(r"<!-- purpose: (.*?) -->", doc.content or "")
                if purpose_match:
                    desc = purpose_match.group(1)
                else:
                    desc = _extract_first_sentence(doc.content)
                lines.append(f"| [Architecture Diagram](diagram-architecture) | {desc} |")

        lines.append("")

    module_docs = docs_by_type.get(DocType.module, [])
    if module_docs:
        lines.append("## Module Documentation")
        lines.append("")
        lines.append("| Module | Description |")
        lines.append("|--------|-------------|")
        for doc in module_docs:
            desc = _extract_first_sentence(doc.content)
            title = doc.title or doc.doc_id
            lines.append(f"| [{title}]({doc.doc_id}) | {desc} |")
        lines.append("")

    diagram_module_docs = [
        doc for doc in diagram_docs if doc.doc_id and doc.doc_id.startswith("diagram-module-")
    ]
    if diagram_module_docs:
        lines.append("## Module Diagrams")
        lines.append("")
        lines.append("| Module | Diagram |")
        lines.append("|--------|---------|")
        for doc in diagram_module_docs:
            module_name = doc.doc_id.replace("diagram-module-", "").replace("-", " ").title()
            lines.append(f"| {module_name} | [{doc.doc_id}]({doc.doc_id}) |")
        lines.append("")

    api_docs = docs_by_type.get(DocType.api, [])
    if api_docs:
        lines.append("## API Reference")
        lines.append("")
        lines.append("| Document | Description |")
        lines.append("|----------|-------------|")
        for doc in api_docs:
            desc = _extract_first_sentence(doc.content)
            lines.append(f"| [{doc.title or doc.doc_id}]({doc.doc_id}) | {desc} |")
        lines.append("")
    else:
        lines.append("## API Reference")
        lines.append("")
        lines.append("_No API documentation registered yet._")
        lines.append("")

    research_docs = docs_by_type.get(DocType.research, [])
    if research_docs:
        lines.append("## Research")
        lines.append("")
        lines.append("| Title | Date |")
        lines.append("|-------|------|")
        for doc in research_docs:
            date = doc.generated_at.strftime("%Y-%m-%d") if doc.generated_at else "—"
            title = doc.title or doc.doc_id
            lines.append(f"| [{title}]({doc.doc_id}) | {date} |")
        lines.append("")
    else:
        lines.append("## Research")
        lines.append("")
        lines.append("_No research documents._")
        lines.append("")

    return "\n".join(lines)


def generate_index_page(project_id: str, session: Session) -> None:
    """Generate or update the code-index ProjectDoc for the given project."""
    doc_service = DocService(session)

    all_docs = doc_service.list_docs(project_id=project_id, limit=500)

    if not all_docs:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        content = (
            f"# Documentation Index — {project_id}\n\n"
            f"<!-- generated: {today} -->\n\n"
            "> [!NOTE]\n> No documentation has been generated for this project yet. "
            'Run "Generate Code Map" from the Code section to get started.'
        )
    else:
        docs_by_type: dict[DocType, list[ProjectDoc]] = {}
        for doc in all_docs:
            docs_by_type.setdefault(doc.doc_type, []).append(doc)

        project = session.get(Project, project_id)
        display_name = project.display_name if project else project_id

        content = _build_index_content(display_name, docs_by_type)

    existing = doc_service.get_doc(project_id, "code-index")
    try:
        if existing is None:
            doc_service.create_doc(
                project_id=project_id,
                doc_id="code-index",
                title=f"Documentation Index — {project_id}",
                doc_type=DocType.architecture,
                tier=DocTier.fully_automated,
                editorial_category=EditorialCategory.technical,
                content=content,
                generated_by="code-understanding:index_gen",
            )
        else:
            doc_service.update_doc(
                project_id=project_id,
                doc_id="code-index",
                title=f"Documentation Index — {project_id}",
                content=content,
                generated_by="code-understanding:index_gen",
            )
        session.commit()
    except Exception as exc:
        logger.warning("Index page generation failed for project %s: %s", project_id, exc)
        session.rollback()
        raise
