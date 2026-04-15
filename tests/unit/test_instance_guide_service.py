"""Unit tests for DocInstanceGuide service methods and _effective_guide merge logic."""

from __future__ import annotations

from unittest.mock import MagicMock

from orch.db.models import DocInstanceGuide
from orch.doc_service import DocService


class TestGetInstanceGuide:
    def test_get_instance_guide_returns_none_when_missing(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        svc = DocService(session)
        result = svc.get_instance_guide("test-proj", "doc001")

        assert result is None
        session.get.assert_called_once_with(DocInstanceGuide, "test-proj:doc001")

    def test_get_instance_guide_returns_content_when_present(self) -> None:
        session = MagicMock()
        mock_guide = MagicMock(spec=DocInstanceGuide)
        mock_guide.guide_md = "# Instance Guide\n\nCustom content."
        session.get.return_value = mock_guide

        svc = DocService(session)
        result = svc.get_instance_guide("test-proj", "doc001")

        assert result == "# Instance Guide\n\nCustom content."
        session.get.assert_called_once_with(DocInstanceGuide, "test-proj:doc001")


class TestSaveInstanceGuide:
    def test_save_instance_guide_inserts_new_row(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        svc = DocService(session)
        result = svc.save_instance_guide("test-proj", "doc001", "# New Guide")

        assert isinstance(result, DocInstanceGuide)
        session.add.assert_called_once()
        session.flush.assert_called_once()
        saved = session.add.call_args[0][0]
        assert saved.doc_id == "test-proj:doc001"
        assert saved.guide_md == "# New Guide"

    def test_save_instance_guide_updates_existing_row(self) -> None:
        session = MagicMock()
        existing = MagicMock(spec=DocInstanceGuide)
        existing.doc_id = "test-proj:doc001"
        existing.guide_md = "# Old Guide"
        session.get.return_value = existing

        svc = DocService(session)
        result = svc.save_instance_guide("test-proj", "doc001", "# Updated Guide")

        assert result is existing
        assert result.guide_md == "# Updated Guide"
        session.add.assert_not_called()
        session.flush.assert_called_once()


class TestDeleteInstanceGuide:
    def test_delete_instance_guide_deletes_existing(self) -> None:
        session = MagicMock()
        existing = MagicMock(spec=DocInstanceGuide)
        existing.doc_id = "test-proj:doc001"
        session.get.return_value = existing

        svc = DocService(session)
        result = svc.delete_instance_guide("test-proj", "doc001")

        assert result is True
        session.delete.assert_called_once_with(existing)
        session.flush.assert_called_once()

    def test_delete_instance_guide_returns_false_when_missing(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        svc = DocService(session)
        result = svc.delete_instance_guide("test-proj", "doc001")

        assert result is False
        session.delete.assert_not_called()


class TestEffectiveGuide:
    def test_effective_guide_instance_wins(self) -> None:
        session = MagicMock()
        mock_instance = MagicMock(spec=DocInstanceGuide)
        mock_instance.guide_md = "# Instance Guide"
        session.get.return_value = mock_instance

        svc = DocService(session)
        result = svc._effective_guide("test-proj", "doc001", "api")

        assert result == "# Instance Guide"

    def test_effective_guide_type_fallback(self) -> None:
        session = MagicMock()
        session.get.side_effect = [None, MagicMock(guide_md="# Type Guide")]

        svc = DocService(session)
        result = svc._effective_guide("test-proj", "doc001", "api")

        assert result == "# Type Guide"

    def test_effective_guide_none_fallback(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        svc = DocService(session)
        result = svc._effective_guide("test-proj", "doc001", "api")

        assert result is None
