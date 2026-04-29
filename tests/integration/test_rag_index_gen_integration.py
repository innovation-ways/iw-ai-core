"""Integration tests for generate_index_page() with a real testcontainer DB.

Verifies DB writes with specific enum values and content assertions — not just
that a doc was created.
"""

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


class TestIndexPageIntegrationDB:
    """Integration tests for generate_index_page() against a real DB."""

    def test_index_page_created_in_db_with_correct_doc_type(self, db_session, test_project):
        """generate_index_page() creates a code-index ProjectDoc with DocType.architecture."""
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
            content="# Architecture Map\n\nThis system provides orchestration.",
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
            content="# Orch Module\n\nHandles work item execution.",
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
        assert index_doc.doc_type == DocType.architecture, (
            f"Expected DocType.architecture, got {index_doc.doc_type}"
        )
        assert index_doc.tier == DocTier.fully_automated, (
            f"Expected DocTier.fully_automated, got {index_doc.tier}"
        )
        assert "## Module Documentation" in index_doc.content, (
            f"Content must contain '## Module Documentation', got: {index_doc.content[:200]}"
        )
        assert "[Orch Module](module-orch)" in index_doc.content
        assert "Shows system components and data flow" in index_doc.content

    def test_index_page_update_doc_on_rerun(self, db_session, test_project):
        """Subsequent calls update the existing code-index doc."""
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

        updated_doc = db_session.execute(
            select(ProjectDoc).where(
                ProjectDoc.project_id == test_project.id,
                ProjectDoc.doc_id == "code-index",
            )
        ).scalar_one_or_none()

        assert updated_doc is not None
        assert updated_doc.title == f"Documentation Index — {test_project.id}"
        assert updated_doc.generated_by == "code-understanding:index_gen"
        assert "## Module Documentation" in updated_doc.content
        assert "[Test Module](module-test)" in updated_doc.content

    def test_index_page_empty_project_no_crash(self, db_session, test_project):
        """Empty project (no docs) generates index with 'No documentation' note without crash."""
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

    def test_index_page_groups_by_doc_type_under_correct_sections(self, db_session, test_project):
        """Index groups docs by type under correct ## sections."""
        from orch.rag.index_gen import generate_index_page

        arch_doc = ProjectDoc(
            id=f"{test_project.id}:architecture-map",
            project_id=test_project.id,
            doc_id="architecture-map",
            title="Architecture Map",
            slug=_slugify("Architecture Map"),
            doc_type=DocType.architecture,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            content="# Architecture Map\n\nOverview.",
            version=1,
            generated_at=datetime.now(UTC),
            generated_by="test",
        )
        db_session.add(arch_doc)

        module_doc = ProjectDoc(
            id=f"{test_project.id}:module-foo",
            project_id=test_project.id,
            doc_id="module-foo",
            title="Foo Module",
            slug=_slugify("Foo Module"),
            doc_type=DocType.module,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            content="# Foo Module\n\nFoo module.",
            version=1,
            generated_at=datetime.now(UTC),
            generated_by="test",
        )
        db_session.add(module_doc)

        api_doc = ProjectDoc(
            id=f"{test_project.id}:api-test",
            project_id=test_project.id,
            doc_id="api-test",
            title="Test API",
            slug=_slugify("Test API"),
            doc_type=DocType.api,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            content="# Test API\n\nREST API.",
            version=1,
            generated_at=datetime.now(UTC),
            generated_by="test",
        )
        db_session.add(api_doc)
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
        assert "## Module Documentation" in index_doc.content
        assert "[Foo Module](module-foo)" in index_doc.content
        assert "## API Reference" in index_doc.content
        assert "[Test API](api-test)" in index_doc.content
