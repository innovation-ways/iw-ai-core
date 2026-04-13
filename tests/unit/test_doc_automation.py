"""Unit tests for F-00013 documentation automation backend.

Tests:
- DocService.find_docs_by_source_path() (exact + glob)
- DocService.get_stale_docs() (git mtime)
- DocService.lint_doc_content()
- trigger_doc_regeneration_on_merge()
- iw docs-check-stale CLI
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from orch.cli.doc_commands import docs_check_stale
from orch.daemon.batch_merge_hooks import trigger_doc_regeneration_on_merge
from orch.db.models import (
    DocStatus,
    EditorialCategory,
    Project,
    ProjectDoc,
)
from orch.doc_service import DocService


class TestFindDocsBySourcePath:
    """Tests for DocService.find_docs_by_source_path()."""

    def test_find_docs_by_source_path_exact_match(self) -> None:
        """Exact path match returns the doc."""
        session = MagicMock()
        doc1 = MagicMock(spec=ProjectDoc)
        doc1.source_paths = ["docs/auth/middleware.py"]
        doc1.status = DocStatus.draft

        doc2 = MagicMock(spec=ProjectDoc)
        doc2.source_paths = ["docs/billing.py"]
        doc2.status = DocStatus.draft

        def mock_query(model: type) -> MagicMock:
            q = MagicMock()
            q.filter.return_value.all.return_value = [doc1, doc2]
            return q

        session.query = mock_query

        svc = DocService(session)
        result = svc.find_docs_by_source_path("proj1", ["docs/auth/middleware.py"])

        assert doc1 in result
        assert doc2 not in result

    def test_find_docs_by_source_path_glob_match(self) -> None:
        """Glob pattern in source_paths matches changed file (segment-wise fnmatch)."""
        session = MagicMock()
        doc1 = MagicMock(spec=ProjectDoc)
        doc1.source_paths = ["docs/auth/*"]
        doc1.status = DocStatus.draft

        doc2 = MagicMock(spec=ProjectDoc)
        doc2.source_paths = ["docs/billing.py"]
        doc2.status = DocStatus.draft

        def mock_query(model: type) -> MagicMock:
            q = MagicMock()
            q.filter.return_value.all.return_value = [doc1, doc2]
            return q

        session.query = mock_query

        svc = DocService(session)
        result = svc.find_docs_by_source_path("proj1", ["docs/auth/middleware/token.py"])

        assert doc1 in result
        assert doc2 not in result

    def test_find_docs_by_source_path_no_match(self) -> None:
        """No matching path returns empty list."""
        session = MagicMock()
        doc1 = MagicMock(spec=ProjectDoc)
        doc1.source_paths = ["docs/auth/middleware.py"]
        doc1.status = DocStatus.draft

        def mock_query(model: type) -> MagicMock:
            q = MagicMock()
            q.filter.return_value.all.return_value = [doc1]
            return q

        session.query = mock_query

        svc = DocService(session)
        result = svc.find_docs_by_source_path("proj1", ["docs/unrelated.py"])

        assert result == []

    def test_find_docs_by_source_path_skips_archived(self) -> None:
        """Archived docs are excluded."""
        session = MagicMock()
        doc1 = MagicMock(spec=ProjectDoc)
        doc1.source_paths = ["docs/auth/middleware.py"]
        doc1.status = DocStatus.archived

        def mock_query(model: type) -> MagicMock:
            q = MagicMock()
            q.filter.return_value.filter.return_value.all.return_value = [doc1]
            return q

        session.query = mock_query

        svc = DocService(session)
        result = svc.find_docs_by_source_path("proj1", ["docs/auth/middleware.py"])

        assert result == []


class TestGetStaleDocs:
    """Tests for DocService.get_stale_docs() with git mtime."""

    def test_get_stale_docs_with_changed_source(self) -> None:
        """Doc is stale when source file has newer commit than generated_at."""
        session = MagicMock()
        doc = MagicMock(spec=ProjectDoc)
        doc.project_id = "proj1"
        doc.doc_id = "module-auth"
        doc.source_paths = ["docs/auth/middleware.py"]
        doc.generated_at = datetime(2026, 1, 1, tzinfo=UTC)
        doc.status = DocStatus.draft

        q = MagicMock()
        q.filter.return_value = q
        q.all.return_value = [doc]
        session.query = MagicMock(return_value=q)

        def run_mock(cmd: list[str], **kwargs: Any) -> MagicMock:
            if "--" in cmd and "docs/auth/middleware.py" in cmd:
                r = MagicMock()
                r.returncode = 0
                r.stdout = "1800000000"
                return r
            r = MagicMock()
            r.returncode = 0
            r.stdout = ""
            return r

        with patch("subprocess.run", side_effect=run_mock):
            svc = DocService(session)
            result = svc.get_stale_docs("proj1", "/fake/repo", threshold_hours=24)

        assert len(result) == 1
        assert result[0][0] == doc
        assert result[0][1] == "docs/auth/middleware.py"

    def test_get_stale_docs_current_doc(self) -> None:
        """No stale docs when source file is older than generated_at."""
        session = MagicMock()
        doc = MagicMock(spec=ProjectDoc)
        doc.project_id = "proj1"
        doc.source_paths = ["docs/auth/middleware.py"]
        doc.generated_at = datetime(2030, 1, 1, tzinfo=UTC)
        doc.status = DocStatus.draft

        def mock_query(model: type) -> MagicMock:
            q = MagicMock()
            q.filter.return_value.all.return_value = [doc]
            return q

        session.query = mock_query

        def run_mock(cmd: list[str], **kwargs: Any) -> MagicMock:
            r = MagicMock()
            r.returncode = 0
            r.stdout = "1700000000"
            return r

        with patch("subprocess.run", side_effect=run_mock):
            svc = DocService(session)
            result = svc.get_stale_docs("proj1", "/fake/repo", threshold_hours=24)

        assert result == []


class TestLintDocContent:
    """Tests for DocService.lint_doc_content()."""

    def test_lint_doc_content_passes_valid_technical(self) -> None:
        """Valid technical doc with all required sections passes."""
        content = """---
title: Auth Middleware
---
## Purpose
This middleware handles auth.

## Architecture
The system uses JWT.

```
def foo():
    pass
```
"""
        svc = DocService(MagicMock())
        warnings = svc.lint_doc_content(content, EditorialCategory.technical)
        assert warnings == []

    def test_lint_doc_content_missing_purpose_section(self) -> None:
        """Missing Purpose section reports warning."""
        content = """---
title: Auth
---
## Architecture
...
"""
        svc = DocService(MagicMock())
        warnings = svc.lint_doc_content(content, EditorialCategory.technical)

        purpose_warnings = [w for w in warnings if w["rule"] == "required_section_purpose"]
        assert len(purpose_warnings) == 1

    def test_lint_doc_content_forbidden_phrase(self) -> None:
        """Forbidden phrase is detected."""
        content = """---
title: Auth
---
## Purpose
This is a cutting-edge solution.
"""
        svc = DocService(MagicMock())
        warnings = svc.lint_doc_content(content, EditorialCategory.technical)

        phrase_warnings = [w for w in warnings if w["rule"] == "forbidden_phrase"]
        assert len(phrase_warnings) == 1
        assert "cutting-edge" in phrase_warnings[0]["message"]

    def test_lint_doc_content_missing_frontmatter(self) -> None:
        """Missing frontmatter is detected."""
        content = """# Auth

## Purpose
...
"""
        svc = DocService(MagicMock())
        warnings = svc.lint_doc_content(content, EditorialCategory.technical)

        fm_warnings = [w for w in warnings if w["rule"] == "frontmatter_required"]
        assert len(fm_warnings) == 1

    def test_lint_doc_content_custom_forbidden_phrases(self) -> None:
        """Custom forbidden phrases are checked."""
        content = """---
title: Auth
---
## Purpose
This is synergy in action.
"""
        svc = DocService(MagicMock())
        warnings = svc.lint_doc_content(
            content, EditorialCategory.technical, forbidden_phrases=["synergy"]
        )

        phrase_warnings = [w for w in warnings if w["rule"] == "forbidden_phrase"]
        assert len(phrase_warnings) == 1


class TestTriggerDocRegenerationOnMerge:
    """Tests for trigger_doc_regeneration_on_merge()."""

    def test_trigger_doc_regeneration_auto_trigger_disabled(self) -> None:
        """Returns [] when auto_trigger_on_merge is False."""
        session = MagicMock()
        batch_item = MagicMock()
        batch_item.batch_id = "B-00042"
        batch_item.work_item_id = "F-00013"

        project = MagicMock(spec=Project)
        project.id = "proj1"
        project.repo_root = "/fake/repo"
        project.config = {"doc_generation": {"auto_trigger_on_merge": False}}

        result = trigger_doc_regeneration_on_merge(session, batch_item, project)
        assert result == []

    def test_trigger_doc_regeneration_creates_jobs(self) -> None:
        """Creates DocGenerationJob for each matched doc."""
        session = MagicMock()
        batch_item = MagicMock()
        batch_item.batch_id = "B-00042"
        batch_item.work_item_id = "F-00013"

        project = MagicMock(spec=Project)
        project.id = "proj1"
        project.repo_root = "/fake/repo"
        project.config = {"doc_generation": {"auto_trigger_on_merge": True}}

        doc = MagicMock(spec=ProjectDoc)
        doc.doc_id = "module-auth"

        def run_mock(cmd: list[str], **kwargs: Any) -> MagicMock:
            r = MagicMock()
            r.returncode = 0
            r.stdout = "docs/auth/middleware.py\n"
            return r

        with (
            patch("subprocess.run", side_effect=run_mock),
            patch.object(DocService, "find_docs_by_source_path", return_value=[doc]),
            patch.object(DocService, "create_doc_job") as create_mock,
        ):
            job = MagicMock()
            job.trigger_reason = None
            create_mock.return_value = job

            result = trigger_doc_regeneration_on_merge(session, batch_item, project)

        assert len(result) == 1


class TestDocsCheckStaleCli:
    """Tests for iw docs-check-stale CLI."""

    def test_docs_check_stale_exits_0_when_current(self) -> None:
        """Exits 0 when no stale docs."""
        session = MagicMock()
        project = MagicMock(spec=Project)
        project.repo_root = "/fake/repo"

        def get_mock(mod: type, key: str) -> Any:
            if mod == Project:
                return project
            return None

        session.get = get_mock

        fake_get_session = MagicMock()
        fake_get_session.return_value.__enter__ = MagicMock(return_value=session)
        fake_get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(DocService, "get_stale_docs", return_value=[]):
            runner = CliRunner()
            result = runner.invoke(
                docs_check_stale,
                ["proj1"],
                obj={"get_session": fake_get_session},
            )

        assert result.exit_code == 0
        assert "All docs are current" in result.output

    def test_docs_check_stale_exits_1_when_stale(self) -> None:
        """Exits 1 when stale docs exist."""
        session = MagicMock()
        project = MagicMock(spec=Project)
        project.repo_root = "/fake/repo"

        def get_mock(mod: type, key: str) -> Any:
            if mod == Project:
                return project
            return None

        session.get = get_mock

        fake_get_session = MagicMock()
        fake_get_session.return_value.__enter__ = MagicMock(return_value=session)
        fake_get_session.return_value.__exit__ = MagicMock(return_value=False)

        doc = MagicMock()
        doc.doc_id = "module-auth"

        stale_entry = (doc, "docs/auth/middleware.py", datetime(2026, 4, 10, tzinfo=UTC))

        with patch.object(DocService, "get_stale_docs", return_value=[stale_entry]):
            runner = CliRunner()
            result = runner.invoke(
                docs_check_stale,
                ["proj1"],
                obj={"get_session": fake_get_session},
            )

        assert result.exit_code == 1
        assert "STALE" in result.output
