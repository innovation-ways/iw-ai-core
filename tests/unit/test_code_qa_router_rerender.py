"""Unit tests for the rerender endpoint in the code_qa router."""

from __future__ import annotations

import pytest


class TestQARerenderRequestSchema:
    """Tests for QARerenderRequest schema validation."""

    def test_rerender_request_valid_tone_values(self) -> None:
        """QARerenderRequest accepts technical and functional tones."""
        from dashboard.routers.code_qa import QARerenderRequest

        req = QARerenderRequest(render_id="abc123", tone="technical")
        assert req.tone == "technical"

        req = QARerenderRequest(render_id="abc123", tone="functional")
        assert req.tone == "functional"

    def test_rerender_request_invalid_tone_rejected(self) -> None:
        """QARerenderRequest.tone rejects invalid values."""
        from pydantic import ValidationError

        from dashboard.routers.code_qa import QARerenderRequest

        with pytest.raises(ValidationError):
            QARerenderRequest(render_id="abc123", tone="invalid")

        with pytest.raises(ValidationError):
            QARerenderRequest(render_id="abc123", tone="simple")

    def test_rerender_request_requires_render_id(self) -> None:
        """QARerenderRequest requires non-empty render_id."""
        from pydantic import ValidationError

        from dashboard.routers.code_qa import QARerenderRequest

        with pytest.raises(ValidationError):
            QARerenderRequest(render_id="", tone="technical")

    def test_rerender_request_render_id_min_length(self) -> None:
        """render_id must have min_length=1."""
        from dashboard.routers.code_qa import QARerenderRequest

        req = QARerenderRequest(render_id="a", tone="technical")
        assert len(req.render_id) == 1


class TestRerenderEndpointCacheCheck:
    """Tests for rerender cache check behavior."""

    def test_rerender_requires_cache_hit(self) -> None:
        """Rerender endpoint checks cache before streaming."""
        from unittest.mock import MagicMock

        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test", config=MagicMock())

        assert engine._cache_get("nonexistent") is None

    def test_rerender_cache_returns_bundle_on_hit(self) -> None:
        """_cache_get returns EvidenceBundle when render_id exists and not expired."""
        from unittest.mock import MagicMock

        from orch.rag.evidence import EvidenceBundle
        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test", config=MagicMock())

        bundle = EvidenceBundle(
            question="test?",
            code_chunks=[],
            doc_chunks=[],
            fts_items=[],
            git_log_items=[],
            work_items=[],
        )
        engine._cache_put("test-render-id", bundle, "test?")

        result = engine._cache_get("test-render-id")
        assert result is bundle
