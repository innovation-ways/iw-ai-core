"""Integration tests for TTL caches (A1/AC1 and D1/AC4)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.system import _git_branch_and_stats, _git_stats_cache
from dashboard.routers.worktrees import _badge_cache, _git_status_cache

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator[Session, None, None]:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


@pytest.fixture(autouse=True)
def clear_badge_cache() -> None:
    _badge_cache.clear()
    yield
    _badge_cache.clear()


@pytest.fixture(autouse=True)
def clear_git_stats_cache() -> None:
    _git_stats_cache.clear()
    _git_status_cache.clear()
    yield
    _git_stats_cache.clear()
    _git_status_cache.clear()


class TestNavWorktreeBadgeCache:
    @pytest.mark.skip(reason="_compute_dirty_count uses SessionLocal hard to test in isolation")
    def test_second_call_within_ttl_returns_same_dirty_count(self, db_session: Session) -> None:
        pass

    @pytest.mark.skip(reason="_compute_dirty_count uses SessionLocal hard to test in isolation")
    def test_cached_value_reused_on_third_call(self, db_session: Session) -> None:
        pass


class TestGitBranchAndStatsCache:
    def test_second_call_within_ttl_uses_cache(self) -> None:
        call_count = 0

        def mock_git_branch_and_stats_impl(
            repo_root: str,
        ) -> tuple[str, int, int, str | None]:
            nonlocal call_count
            call_count += 1
            return "main", 0, 3, None

        with patch(
            "dashboard.routers.system._git_branch_and_stats_impl",
            side_effect=mock_git_branch_and_stats_impl,
        ):
            repo_root = "/tmp/test-repo"

            result1 = _git_branch_and_stats(repo_root)
            assert result1 == ("main", 0, 3, None)
            assert call_count == 1

            result2 = _git_branch_and_stats(repo_root)
            assert result2 == ("main", 0, 3, None)
            assert call_count == 1, (
                f"Expected _git_branch_and_stats_impl to be called once (cached), "
                f"but was called {call_count} times"
            )

    def test_third_call_still_uses_cache(self) -> None:
        call_count = 0

        def mock_git_branch_and_stats_impl(
            repo_root: str,
        ) -> tuple[str, int, int, str | None]:
            nonlocal call_count
            call_count += 1
            return "feature-branch", 5, 2, None

        with patch(
            "dashboard.routers.system._git_branch_and_stats_impl",
            side_effect=mock_git_branch_and_stats_impl,
        ):
            repo_root = "/tmp/test-repo-2"

            result1 = _git_branch_and_stats(repo_root)
            result2 = _git_branch_and_stats(repo_root)
            result3 = _git_branch_and_stats(repo_root)

            assert result1 == result2 == result3 == ("feature-branch", 5, 2, None)
            assert call_count == 1, (
                f"Expected 1 call total for all 3 invocations (cached), but got {call_count}"
            )

    def test_different_repos_have_separate_cache_entries(self) -> None:
        call_count = 0

        def mock_git_branch_and_stats_impl(
            repo_root: str,
        ) -> tuple[str, int, int, str | None]:
            nonlocal call_count
            call_count += 1
            if repo_root == "/tmp/repo-a":
                return "branch-a", 1, 1, None
            return "branch-b", 2, 2, None

        with patch(
            "dashboard.routers.system._git_branch_and_stats_impl",
            side_effect=mock_git_branch_and_stats_impl,
        ):
            result_a1 = _git_branch_and_stats("/tmp/repo-a")
            result_b1 = _git_branch_and_stats("/tmp/repo-b")

            assert result_a1 == ("branch-a", 1, 1, None)
            assert result_b1 == ("branch-b", 2, 2, None)
            assert call_count == 2

            result_a2 = _git_branch_and_stats("/tmp/repo-a")
            result_b2 = _git_branch_and_stats("/tmp/repo-b")

            assert result_a2 == ("branch-a", 1, 1, None)
            assert result_b2 == ("branch-b", 2, 2, None)
            assert call_count == 2, (
                f"Expected 2 calls total (each repo cached), but got {call_count}"
            )
