"""Unit tests for DocTypeGuide service methods."""

from __future__ import annotations

from unittest.mock import MagicMock

from orch.db.models import DocTypeGuide
from orch.doc_service import DocService


class TestGetTypeGuide:
    def test_get_type_guide_returns_none_when_missing(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        svc = DocService(session)
        result = svc.get_type_guide("marketing")

        assert result is None
        session.get.assert_called_once_with(DocTypeGuide, "marketing")

    def test_get_type_guide_returns_content_when_present(self) -> None:
        session = MagicMock()
        mock_guide = MagicMock(spec=DocTypeGuide)
        mock_guide.guide_md = "# Marketing Guide\n\nUse a friendly tone."
        session.get.return_value = mock_guide

        svc = DocService(session)
        result = svc.get_type_guide("marketing")

        assert result == "# Marketing Guide\n\nUse a friendly tone."
        session.get.assert_called_once_with(DocTypeGuide, "marketing")


class TestSaveTypeGuide:
    def test_save_type_guide_inserts_new_row(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        svc = DocService(session)
        result = svc.save_type_guide("marketing", "# New Guide")

        assert isinstance(result, DocTypeGuide)
        session.add.assert_called_once()
        session.flush.assert_called_once()
        saved = session.add.call_args[0][0]
        assert saved.doc_type == "marketing"
        assert saved.guide_md == "# New Guide"

    def test_save_type_guide_updates_existing_row(self) -> None:
        session = MagicMock()
        existing = MagicMock(spec=DocTypeGuide)
        existing.doc_type = "marketing"
        existing.guide_md = "# Old Guide"
        session.get.return_value = existing

        svc = DocService(session)
        result = svc.save_type_guide("marketing", "# Updated Guide")

        assert result is existing
        assert result.guide_md == "# Updated Guide"
        session.add.assert_not_called()
        session.flush.assert_called_once()
