"""Integration tests for orch.rag.index_gen."""

from datetime import UTC, datetime

from sqlalchemy import select

from orch.db.models import DocTier, DocType, EditorialCategory, ProjectDoc


def _slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = slug.replace(" ", "-")
    result = []
    for ch in slug:
        if ch.isalnum() or ch in "-_":
            result.append(ch)
        else:
            result.append("-")
    slug = "".join(result)
    slug = "".join(c for c in slug if c.isalnum() or c == "-").strip("-")
    if not slug:
        slug = "untitled"
    return slug


class TestGenerateIndexPageIntegration:
    """Integration tests for generate_index_page() with a real testcontainer DB."""

    def test_creates_code_index_doc_for_project_with_docs(self, db_session, test_project):
        from orch.rag.index_gen import generate_index_page

        arch_doc = ProjectDoc(
            id=f"{test_project.id}:architecture-map",
            project_id=test_project.id,
            doc_id="architecture-map",
            title="Test Project — Architecture Map",
            slug=_slugify("Test Project — Architecture Map"),
            doc_type=DocType.architecture,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            content="# Architecture Map\n\nThis system provides orchestration for AI agents.",
            version=1,
            generated_at=datetime.now(UTC),
            generated_by="test",
        )
        db_session.add(arch_doc)

        module_doc = ProjectDoc(
            id=f"{test_project.id}:module-orch",
            project_id=test_project.id,
            doc_id="module-orch",
            title="Orch Module",
            slug=_slugify("Orch Module"),
            doc_type=DocType.module,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            content="# Orch Module\n\nHandles work item execution and agent orchestration.",
            version=1,
            generated_at=datetime.now(UTC),
            generated_by="test",
        )
        db_session.add(module_doc)

        diagram_doc = ProjectDoc(
            id=f"{test_project.id}:diagram-architecture",
            project_id=test_project.id,
            doc_id="diagram-architecture",
            title="Test Project — Architecture Diagram",
            slug=_slugify("Test Project — Architecture Diagram"),
            doc_type=DocType.diagram,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            content="<!-- purpose: Shows system components and data flow -->",
            version=1,
            generated_at=datetime.now(UTC),
            generated_by="test",
        )
        db_session.add(diagram_doc)

        db_session.flush()

        generate_index_page(test_project.id, db_session)
        db_session.commit()

        index_doc = db_session.execute(
            select(ProjectDoc).where(
                ProjectDoc.project_id == test_project.id,
                ProjectDoc.doc_id == "code-index",
            )
        ).scalar_one_or_none()

        assert index_doc is not None
        assert index_doc.doc_type == DocType.architecture
        assert index_doc.generated_by == "code-understanding:index_gen"
        assert "## Module Documentation" in index_doc.content
        assert "[Orch Module](module-orch)" in index_doc.content
        assert "Shows system components and data flow" in index_doc.content

    def test_updates_existing_code_index_doc(self, db_session, test_project):
        from orch.rag.index_gen import generate_index_page

        existing_doc = ProjectDoc(
            id=f"{test_project.id}:code-index",
            project_id=test_project.id,
            doc_id="code-index",
            title="Old Title",
            slug=_slugify("Old Title"),
            doc_type=DocType.architecture,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            content="Old content",
            version=1,
            generated_at=datetime.now(UTC),
            generated_by="old-generator",
        )
        db_session.add(existing_doc)
        db_session.flush()

        module_doc = ProjectDoc(
            id=f"{test_project.id}:module-test",
            project_id=test_project.id,
            doc_id="module-test",
            title="Test Module",
            slug=_slugify("Test Module"),
            doc_type=DocType.module,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            content="# Test Module\n\nA test module.",
            version=1,
            generated_at=datetime.now(UTC),
            generated_by="test",
        )
        db_session.add(module_doc)
        db_session.flush()

        generate_index_page(test_project.id, db_session)
        db_session.commit()

        index_doc = db_session.execute(
            select(ProjectDoc).where(
                ProjectDoc.project_id == test_project.id,
                ProjectDoc.doc_id == "code-index",
            )
        ).scalar_one_or_none()

        assert index_doc is not None
        assert index_doc.title == f"Documentation Index — {test_project.id}"
        assert "## Module Documentation" in index_doc.content
        assert index_doc.generated_by == "code-understanding:index_gen"

    def test_empty_project_shows_no_documentation_note(self, db_session, test_project):
        from orch.rag.index_gen import generate_index_page

        generate_index_page(test_project.id, db_session)
        db_session.commit()

        index_doc = db_session.execute(
            select(ProjectDoc).where(
                ProjectDoc.project_id == test_project.id,
                ProjectDoc.doc_id == "code-index",
            )
        ).scalar_one_or_none()

        assert index_doc is not None
        assert "No documentation has been generated" in index_doc.content

    def test_api_reference_shows_no_docs_when_empty(self, db_session, test_project):
        from orch.rag.index_gen import generate_index_page

        arch_doc = ProjectDoc(
            id=f"{test_project.id}:architecture-map",
            project_id=test_project.id,
            doc_id="architecture-map",
            title="Test Project — Architecture Map",
            slug=_slugify("Test Project — Architecture Map"),
            doc_type=DocType.architecture,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            content="# Architecture Map\n\nOverview.",
            version=1,
            generated_at=datetime.now(UTC),
            generated_by="test",
        )
        db_session.add(arch_doc)
        db_session.flush()

        generate_index_page(test_project.id, db_session)
        db_session.commit()

        index_doc = db_session.execute(
            select(ProjectDoc).where(
                ProjectDoc.project_id == test_project.id,
                ProjectDoc.doc_id == "code-index",
            )
        ).scalar_one_or_none()

        assert index_doc is not None
        assert "_No API documentation registered yet._" in index_doc.content

    def test_research_section_shows_no_docs_when_empty(self, db_session, test_project):
        from orch.rag.index_gen import generate_index_page

        arch_doc = ProjectDoc(
            id=f"{test_project.id}:architecture-map",
            project_id=test_project.id,
            doc_id="architecture-map",
            title="Test Project — Architecture Map",
            slug=_slugify("Test Project — Architecture Map"),
            doc_type=DocType.architecture,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            content="# Architecture Map\n\nOverview.",
            version=1,
            generated_at=datetime.now(UTC),
            generated_by="test",
        )
        db_session.add(arch_doc)
        db_session.flush()

        generate_index_page(test_project.id, db_session)
        db_session.commit()

        index_doc = db_session.execute(
            select(ProjectDoc).where(
                ProjectDoc.project_id == test_project.id,
                ProjectDoc.doc_id == "code-index",
            )
        ).scalar_one_or_none()

        assert index_doc is not None
        assert "_No research documents._" in index_doc.content
