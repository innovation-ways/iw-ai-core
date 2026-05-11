"""Unit tests for DocTypeGuide service methods."""

from __future__ import annotations

from unittest.mock import MagicMock

from orch.db.models import DocInstanceGuide, DocTypeGuide
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


class TestEffectiveGuide:
    def test_effective_guide_falls_back_to_default_when_no_specific_guide(self) -> None:
        """FAILS before fix: _effective_guide returns None when neither an instance
        guide nor a doc_type-keyed guide exists, even though a '_default' row exists."""
        default_guide = MagicMock(spec=DocTypeGuide)
        default_guide.guide_md = "# Global Editorial Guidelines\n..."

        def fake_get(model, key):
            if model is DocInstanceGuide:
                return None  # no per-doc instance guide
            if model is DocTypeGuide and key == "diagram":
                return None  # no diagram-specific guide
            if model is DocTypeGuide and key == "_default":
                return default_guide
            return None

        session = MagicMock()
        session.get.side_effect = fake_get
        svc = DocService(session)

        result = svc._effective_guide("iw-ai-core", "diagram-architecture", "diagram")
        assert result == "# Global Editorial Guidelines\n..."  # was None before the fix

    def test_effective_guide_returns_instance_guide_when_present(self) -> None:
        """Regression: instance guide takes priority over doc_type guide and _default."""
        instance_guide = MagicMock(spec=DocInstanceGuide)
        instance_guide.guide_md = "# Instance Guide\nspecific to this doc"

        session = MagicMock()
        session.get.return_value = instance_guide
        svc = DocService(session)

        result = svc._effective_guide("iw-ai-core", "diagram-architecture", "diagram")
        assert result == "# Instance Guide\nspecific to this doc"

    def test_effective_guide_returns_doc_type_guide_when_no_instance_guide(
        self,
    ) -> None:
        """Regression: doc_type guide is used when no instance guide exists."""
        type_guide = MagicMock(spec=DocTypeGuide)
        type_guide.guide_md = "# Diagram Type Guide\nfor all diagram docs"

        def fake_get(model, key):
            if model is DocInstanceGuide:
                return None
            if model is DocTypeGuide and key == "diagram":
                return type_guide
            return None

        session = MagicMock()
        session.get.side_effect = fake_get
        svc = DocService(session)

        result = svc._effective_guide("iw-ai-core", "diagram-architecture", "diagram")
        assert result == "# Diagram Type Guide\nfor all diagram docs"

    def test_effective_guide_returns_none_when_no_guide_exists(self) -> None:
        """When no instance, doc_type, or _default guide exists, return None."""
        session = MagicMock()
        session.get.return_value = None
        svc = DocService(session)

        result = svc._effective_guide("iw-ai-core", "any-doc", "any-type")
        assert result is None
