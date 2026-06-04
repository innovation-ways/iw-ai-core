"""Unit tests for _history_items in project_pages.

Sorting is now handled client-side (JS). These tests verify
that the function accepts its current parameters and returns
results from the DB without errors.
"""

from __future__ import annotations

from unittest.mock import MagicMock


class TestHistoryItems:
    """Tests for _history_items() query and filter logic."""

    def test_accepts_all_filters_none(self) -> None:
        """Calling with all filters as None must not raise."""
        from dashboard.routers.project_pages import _history_items

        mock_db = MagicMock()

        _history_items(
            project_id="test-proj",
            db=mock_db,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
        )

        assert mock_db.scalars.called, "db.scalars should have been called"

    def test_accepts_type_filter(self) -> None:
        """Passing a type_filter value must not raise."""
        from dashboard.routers.project_pages import _history_items

        mock_db = MagicMock()

        _history_items(
            project_id="test-proj",
            db=mock_db,
            type_filter="feature",
            status_filter=None,
            date_from=None,
            date_to=None,
        )

        assert mock_db.scalars.called

    def test_accepts_status_filter(self) -> None:
        """Passing a status_filter value must not raise."""
        from dashboard.routers.project_pages import _history_items

        mock_db = MagicMock()

        _history_items(
            project_id="test-proj",
            db=mock_db,
            type_filter=None,
            status_filter="completed",
            date_from=None,
            date_to=None,
        )

        assert mock_db.scalars.called
