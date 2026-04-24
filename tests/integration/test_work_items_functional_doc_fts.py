"""Integration tests for functional_doc FTS trigger and migration round-trip."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    FUNCTIONAL_DOC_FTS_FUNCTION_SQL,
    FUNCTIONAL_DOC_FTS_TRIGGER_SQL,
    PROJECT_DOCS_FTS_FUNCTION_SQL,
    PROJECT_DOCS_FTS_TRIGGER_SQL,
    Base,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session


class TestFunctionalDocFTS:
    """Test functional_doc_search FTS trigger behaviour."""

    def test_insert_populates_search_vector(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Insert with title and functional_doc_content -> functional_doc_search contains both."""
        item = WorkItem(
            project_id=test_project.id,
            id="F-TEST-001",
            type=WorkItemType.Feature,
            title="Hello",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            functional_doc_content="World",
        )
        db_session.add(item)
        db_session.flush()

        result = db_session.execute(
            text(
                "SELECT functional_doc_search::text FROM work_items "
                "WHERE project_id = :project_id AND id = :id"
            ),
            {"project_id": test_project.id, "id": "F-TEST-001"},
        )
        row = result.fetchone()
        assert row is not None
        search_text = row[0]
        assert search_text is not None
        assert "'hello'" in search_text
        assert "'world'" in search_text

    def test_update_functional_doc_content_regenerates_search(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Update only functional_doc_content -> search vector re-generates."""
        item = WorkItem(
            project_id=test_project.id,
            id="F-TEST-002",
            type=WorkItemType.Feature,
            title="Title Only",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            functional_doc_content="Initial",
        )
        db_session.add(item)
        db_session.flush()

        db_session.execute(
            text(
                "UPDATE work_items SET functional_doc_content = 'Updated' "
                "WHERE project_id = :project_id AND id = :id"
            ),
            {"project_id": test_project.id, "id": "F-TEST-002"},
        )
        db_session.commit()

        result = db_session.execute(
            text(
                "SELECT functional_doc_search::text FROM work_items "
                "WHERE project_id = :project_id AND id = :id"
            ),
            {"project_id": test_project.id, "id": "F-TEST-002"},
        )
        row = result.fetchone()
        assert row is not None
        search_text = row[0]
        assert "'updat'" in search_text
        assert "'initial'" not in search_text

    def test_update_title_regenerates_search(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Update only title -> search vector re-generates with new title lexeme."""
        item = WorkItem(
            project_id=test_project.id,
            id="F-TEST-003",
            type=WorkItemType.Feature,
            title="Old Title",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            functional_doc_content="Content Here",
        )
        db_session.add(item)
        db_session.flush()

        db_session.execute(
            text(
                "UPDATE work_items SET title = 'New Title' "
                "WHERE project_id = :project_id AND id = :id"
            ),
            {"project_id": test_project.id, "id": "F-TEST-003"},
        )
        db_session.commit()

        result = db_session.execute(
            text(
                "SELECT functional_doc_search::text FROM work_items "
                "WHERE project_id = :project_id AND id = :id"
            ),
            {"project_id": test_project.id, "id": "F-TEST-003"},
        )
        row = result.fetchone()
        assert row is not None
        search_text = row[0]
        assert "'new'" in search_text
        assert "'old'" not in search_text
        assert "'content'" in search_text

    def test_gin_index_query_returns_row(self, db_session: Session, test_project: Project) -> None:
        """GIN index query returns the correct row for a term in functional_doc_content."""
        item = WorkItem(
            project_id=test_project.id,
            id="F-TEST-004",
            type=WorkItemType.Feature,
            title="Test Item",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            functional_doc_content="Secret Recipe",
        )
        db_session.add(item)
        db_session.flush()
        db_session.commit()

        result = db_session.execute(
            text(
                "SELECT id FROM work_items "
                "WHERE functional_doc_search @@ to_tsquery('english', 'recipe')"
            )
        )
        rows = result.fetchall()
        assert any(r[0] == "F-TEST-004" for r in rows)

    def test_independence_from_design_doc_search(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Insert with only design_doc_content -> functional_doc_search has only title lexemes."""
        item = WorkItem(
            project_id=test_project.id,
            id="F-TEST-005",
            type=WorkItemType.Feature,
            title="Standalone Title",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            design_doc_content="foo",
        )
        db_session.add(item)
        db_session.flush()
        db_session.commit()

        result_design = db_session.execute(
            text(
                "SELECT design_doc_search::text FROM work_items "
                "WHERE project_id = :project_id AND id = :id"
            ),
            {"project_id": test_project.id, "id": "F-TEST-005"},
        )
        design_row = result_design.fetchone()
        assert design_row is not None
        design_search_text = design_row[0]
        assert design_search_text is not None
        assert "'foo'" in design_search_text

        result_func = db_session.execute(
            text(
                "SELECT functional_doc_search::text FROM work_items "
                "WHERE project_id = :project_id AND id = :id"
            ),
            {"project_id": test_project.id, "id": "F-TEST-005"},
        )
        func_row = result_func.fetchone()
        assert func_row is not None
        func_search_text = func_row[0]
        assert func_search_text is not None
        assert "'standalon'" in func_search_text
        assert "'titl'" in func_search_text
        assert "'foo'" not in func_search_text

    def test_bulk_insert_search_vectors(self, db_session: Session, test_project: Project) -> None:
        """Bulk insert 10 items -> every row's functional_doc_search matches expectation."""
        items = [
            WorkItem(
                project_id=test_project.id,
                id=f"F-BULK-{i:03d}",
                type=WorkItemType.Feature,
                title=f"Bulk Item {i}",
                status=WorkItemStatus.draft,
                phase=WorkItemPhase.active,
                functional_doc_content=f"Bulk content word{i} term{i}",
            )
            for i in range(10)
        ]
        db_session.add_all(items)
        db_session.flush()
        db_session.commit()

        for i in range(10):
            result = db_session.execute(
                text(
                    "SELECT functional_doc_search::text FROM work_items "
                    "WHERE project_id = :project_id AND id = :id"
                ),
                {"project_id": test_project.id, "id": f"F-BULK-{i:03d}"},
            )
            row = result.fetchone()
            assert row is not None, f"F-BULK-{i:03d} not found"
            search_text = row[0]
            assert search_text is not None, f"F-BULK-{i:03d} search vector is NULL"
            assert "'bulk'" in search_text, f"F-BULK-{i:03d} missing 'bulk' lexeme"
            assert "'item'" in search_text, f"F-BULK-{i:03d} missing 'item' lexeme"
            assert f"'{i}'" in search_text or f"word{i}" in search_text

    def test_gin_index_used_for_search_query(
        self, db_session: Session, test_project: Project
    ) -> None:
        """EXPLAIN shows GIN index is used for @@ query (enable_seqscan=off for small tables)."""
        item = WorkItem(
            project_id=test_project.id,
            id="F-TEST-GIN",
            type=WorkItemType.Feature,
            title="Gin Index Test",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            functional_doc_content="UniqueTermForGinSearch",
        )
        db_session.add(item)
        db_session.flush()
        db_session.commit()

        with db_session.connection() as conn:
            conn.execute(text("SET enable_seqscan = off"))
            try:
                result = conn.execute(
                    text(
                        "EXPLAIN SELECT id FROM work_items WHERE "
                        "functional_doc_search @@ to_tsquery('english', 'UniqueTermForGinSearch')"
                    )
                )
                rows = [r[0] for r in result.fetchall()]
                plan = " ".join(rows)
                assert "idx_work_items_functional_doc_search" in plan, (
                    f"GIN index not hit in plan: {plan}"
                )
            finally:
                conn.execute(text("RESET enable_seqscan"))
                conn.commit()


class TestFunctionalDocMigrationRoundTrip:
    """Test that the F-00059 migration is cleanly reversible."""

    def _create_engine(self, pg: PostgresContainer) -> Engine:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        return create_engine(url, pool_pre_ping=True)

    def _run_upgrade(self, engine: Engine) -> None:
        """Run the F-00059 upgrade SQL directly against the given engine.

        Note: function/trigger creation is idempotent (CREATE OR REPLACE / DROP IF EXISTS).
        """
        with engine.connect() as conn:
            conn.execute(
                text(
                    "ALTER TABLE work_items ADD COLUMN IF NOT EXISTS functional_doc_path TEXT NULL"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE work_items ADD COLUMN IF NOT EXISTS "
                    "functional_doc_content TEXT NULL"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE work_items ADD COLUMN IF NOT EXISTS "
                    "functional_doc_search TSVECTOR NULL"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_work_items_functional_doc_search "
                    "ON work_items USING gin (functional_doc_search)"
                )
            )
            conn.execute(text(FUNCTIONAL_DOC_FTS_FUNCTION_SQL))
            conn.execute(
                text("DROP TRIGGER IF EXISTS work_items_functional_doc_search_trg ON work_items")
            )
            conn.execute(text(FUNCTIONAL_DOC_FTS_TRIGGER_SQL))
            conn.commit()

    def _run_downgrade(self, engine: Engine) -> None:
        """Run the F-00059 downgrade SQL directly against the given engine."""
        with engine.connect() as conn:
            conn.execute(text("DROP INDEX IF EXISTS idx_work_items_functional_doc_search"))
            conn.execute(
                text("DROP TRIGGER IF EXISTS work_items_functional_doc_search_trg ON work_items")
            )
            conn.execute(text("DROP FUNCTION IF EXISTS work_items_functional_doc_search_update()"))
            conn.execute(text("ALTER TABLE work_items DROP COLUMN IF EXISTS functional_doc_search"))
            conn.execute(
                text("ALTER TABLE work_items DROP COLUMN IF EXISTS functional_doc_content")
            )
            conn.execute(text("ALTER TABLE work_items DROP COLUMN IF EXISTS functional_doc_path"))
            conn.commit()

    def test_functional_doc_migration_round_trip(self) -> None:
        """Upgrade -> populate data -> downgrade -> verify clean state -> upgrade again succeeds."""
        pg = PostgresContainer("postgres:15-alpine")
        pg.start()
        try:
            engine = self._create_engine(pg)

            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
                conn.commit()

            Base.metadata.create_all(engine)

            with engine.connect() as conn:
                conn.execute(text(FTS_FUNCTION_SQL))
                conn.execute(text(FTS_TRIGGER_SQL))
                conn.execute(text(PROJECT_DOCS_FTS_FUNCTION_SQL))
                conn.execute(text(PROJECT_DOCS_FTS_TRIGGER_SQL))
                conn.execute(text(FUNCTIONAL_DOC_FTS_FUNCTION_SQL))
                conn.execute(text(FUNCTIONAL_DOC_FTS_TRIGGER_SQL))
                conn.commit()

            self._run_upgrade(engine)

            with engine.connect() as conn:
                conn.execute(
                    text(
                        "INSERT INTO projects (id, display_name, repo_root, config) "
                        "VALUES ('test-proj', 'Test', '/repos/test', '{}')"
                    )
                )
                conn.commit()

                conn.execute(
                    text(
                        "INSERT INTO work_items "
                        "(project_id, id, type, title, status, phase, functional_doc_content) "
                        "VALUES ('test-proj', 'F-TEST-100', 'Feature', 'Test Item', "
                        "'draft', 'active', 'Functional Content Here')"
                    )
                )
                conn.commit()

                result = conn.execute(
                    text(
                        "SELECT functional_doc_search FROM work_items "
                        "WHERE project_id = 'test-proj' AND id = 'F-TEST-100'"
                    )
                )
                row = result.fetchone()
                assert row is not None
                assert row[0] is not None

            self._run_downgrade(engine)

            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'work_items' AND column_name IN "
                        "('functional_doc_path', 'functional_doc_content', 'functional_doc_search')"
                    )
                )
                remaining = {r[0] for r in result.fetchall()}
                assert remaining == set(), f"Columns still exist: {remaining}"

                result = conn.execute(
                    text(
                        "SELECT 1 FROM pg_trigger "
                        "WHERE tgname = 'work_items_functional_doc_search_trg'"
                    )
                )
                assert result.fetchone() is None, "Trigger still exists"

                result = conn.execute(
                    text(
                        "SELECT 1 FROM pg_proc "
                        "WHERE proname = 'work_items_functional_doc_search_update'"
                    )
                )
                assert result.fetchone() is None, "Function still exists"

                result = conn.execute(
                    text(
                        "SELECT 1 FROM pg_indexes "
                        "WHERE indexname = 'idx_work_items_functional_doc_search'"
                    )
                )
                assert result.fetchone() is None, "Index still exists"

            self._run_upgrade(engine)

            with engine.connect() as conn:
                conn.execute(
                    text(
                        "INSERT INTO work_items "
                        "(project_id, id, type, title, status, phase, functional_doc_content) "
                        "VALUES ('test-proj', 'F-TEST-101', 'Feature', 'After Downgrade', "
                        "'draft', 'active', 'Content After Re-upgrade')"
                    )
                )
                conn.commit()

                result = conn.execute(
                    text(
                        "SELECT functional_doc_search FROM work_items "
                        "WHERE project_id = 'test-proj' AND id = 'F-TEST-101'"
                    )
                )
                row = result.fetchone()
                assert row is not None, "New row should have functional_doc_search after re-upgrade"
                assert row[0] is not None, "functional_doc_search should not be NULL for new row"

            engine.dispose()
        finally:
            pg.stop()
