"""Integration tests for orch.services.monitoring — list_jobs service tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from orch.db.models import Project


class TestListJobs:
    """Covers the list_jobs service function output shape."""

    def test_list_jobs_returns_expected_shape(self, db_session: Any, test_project: Project) -> None:
        """Verifies that list_jobs returns exact field values for an empty project."""
        from orch.services.monitoring import list_jobs

        result = list_jobs(db_session, test_project.id)
        assert result["total"] == 0
        assert result["page"] == 1
        assert result["page_size"] == 25
        assert result["jobs"] == []

    def test_list_jobs_returns_list_of_dicts(self, db_session: Any, test_project: Project) -> None:
        """Verifies that list_jobs returns an empty jobs list when the project has no jobs."""
        from orch.services.monitoring import list_jobs

        result = list_jobs(db_session, test_project.id)
        assert result["jobs"] == []

    def test_list_jobs_default_pagination(self, db_session: Any, test_project: Project) -> None:
        """Verifies that list_jobs defaults to page=1 and page_size=25."""
        from orch.services.monitoring import list_jobs

        result = list_jobs(db_session, test_project.id)
        assert result["page"] == 1
        assert result["page_size"] == 25

    def test_list_jobs_empty_project_has_zero_total(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that an empty project returns total=0 from list_jobs."""
        from orch.services.monitoring import list_jobs

        result = list_jobs(db_session, test_project.id)
        assert result["total"] == 0
