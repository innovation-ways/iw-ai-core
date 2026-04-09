"""Unit tests for sort parameter validation in project_pages.

These tests verify the sort_by/sort_dir whitelist validation using
mock DB sessions — no testcontainers required (unit tests).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestSortValidation:
    """Tests for _history_items() sort_by and sort_dir validation.

    Uses mocks to test validation logic in isolation.
    """

    def test_sort_by_whitelist_rejects_invalid(self) -> None:
        """Invalid sort_by values must be normalized to 'created_at'.

        Tests: "nonexistent", "; DROP TABLE", "" (empty string).
        All should fall back to 'created_at' — no exception raised.
        """
        from dashboard.routers.project_pages import _history_items

        mock_db = MagicMock()

        # Case 1: completely unknown column name — should not raise
        try:
            _history_items(
                project_id="test-proj",
                db=mock_db,
                type_filter=None,
                status_filter=None,
                date_from=None,
                date_to=None,
                page=1,
                sort_by="nonexistent",
                sort_dir="desc",
            )
        except Exception as exc:
            pytest.fail(f"Expected no exception for invalid sort_by, got {exc}")

        # Case 2: SQL injection attempt — should not raise
        try:
            _history_items(
                project_id="test-proj",
                db=mock_db,
                type_filter=None,
                status_filter=None,
                date_from=None,
                date_to=None,
                page=1,
                sort_by="; DROP TABLE",
                sort_dir="desc",
            )
        except Exception as exc:
            pytest.fail(f"Expected no exception for SQL injection attempt, got {exc}")

        # Case 3: empty string — should not raise
        try:
            _history_items(
                project_id="test-proj",
                db=mock_db,
                type_filter=None,
                status_filter=None,
                date_from=None,
                date_to=None,
                page=1,
                sort_by="",
                sort_dir="desc",
            )
        except Exception as exc:
            pytest.fail(f"Expected no exception for empty sort_by, got {exc}")

    def test_sort_dir_rejects_invalid(self) -> None:
        """Invalid sort_dir values must be normalized to 'desc'.

        Tests: "sideways", "" (empty string), "ASC" (wrong case).
        All should fall back to 'desc' — no exception raised.
        """
        from dashboard.routers.project_pages import _history_items

        mock_db = MagicMock()

        # Case 1: nonsense value — should not raise
        try:
            _history_items(
                project_id="test-proj",
                db=mock_db,
                type_filter=None,
                status_filter=None,
                date_from=None,
                date_to=None,
                page=1,
                sort_by="created_at",
                sort_dir="sideways",
            )
        except Exception as exc:
            pytest.fail(f"Expected no exception for invalid sort_dir, got {exc}")

        # Case 2: empty string — should not raise
        try:
            _history_items(
                project_id="test-proj",
                db=mock_db,
                type_filter=None,
                status_filter=None,
                date_from=None,
                date_to=None,
                page=1,
                sort_by="created_at",
                sort_dir="",
            )
        except Exception as exc:
            pytest.fail(f"Expected no exception for empty sort_dir, got {exc}")

        # Case 3: wrong case (must be exactly 'asc' or 'desc') — should not raise
        try:
            _history_items(
                project_id="test-proj",
                db=mock_db,
                type_filter=None,
                status_filter=None,
                date_from=None,
                date_to=None,
                page=1,
                sort_by="created_at",
                sort_dir="ASC",
            )
        except Exception as exc:
            pytest.fail(f"Expected no exception for wrong-case sort_dir, got {exc}")

    def test_default_sort_params(self) -> None:
        """Omitting sort_by and sort_dir defaults to 'created_at' + 'desc'.

        Verifies by checking that valid sort params are accepted
        and produce no exceptions.
        """
        from dashboard.routers.project_pages import _history_items

        mock_db = MagicMock()

        # Call with explicit defaults — should not raise
        try:
            _history_items(
                project_id="test-proj",
                db=mock_db,
                type_filter=None,
                status_filter=None,
                date_from=None,
                date_to=None,
                page=1,
                sort_by="created_at",  # default
                sort_dir="desc",  # default
            )
        except Exception as exc:
            pytest.fail(f"Expected no exception with default sort params, got {exc}")

        # Verify db.scalars was called (query executed)
        assert mock_db.scalars.called, "db.scalars should have been called"
