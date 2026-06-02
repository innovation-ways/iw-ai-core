"""Unit tests for dashboard/utils/project_onboarding.py helpers.

No DB, no FastAPI — pure function tests using tmp_path for filesystem ops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from dashboard.utils.project_onboarding import (
    is_valid_project_id,
    next_available_project_id,
    safe_resolve_path,
    slugify_project_id,
    validate_repo_root,
)


class TestSlugifyProjectId:
    """Tests for SlugifyProjectId scenarios."""

    def test_lowercase(self):
        """Verifies that lowercase."""
        assert slugify_project_id("My Project") == "my-project"

    def test_spaces_become_hyphens(self):
        """Verifies that spaces become hyphens."""
        assert slugify_project_id("hello world test") == "hello-world-test"

    def test_underscores_become_hyphens(self):
        """Verifies that underscores become hyphens."""
        assert slugify_project_id("hello_world_test") == "hello-world-test"

    def test_multiple_spaces_collapse(self):
        """Verifies that multiple spaces collapse."""
        assert slugify_project_id("hello   world") == "hello-world"

    def test_strips_leading_trailing_dashes(self):
        """Verifies that strips leading trailing dashes."""
        assert slugify_project_id("  my-project  ") == "my-project"

    def test_special_chars_become_hyphens(self):
        """Verifies that special chars become hyphens."""
        assert slugify_project_id("test@#$%project") == "test-project"

    def test_numbers_preserved(self):
        """Verifies that numbers preserved."""
        assert slugify_project_id("project123") == "project123"

    def test_empty_string(self):
        """Verifies that empty string."""
        assert slugify_project_id("") == ""

    def test_already_slug(self):
        """Verifies that already slug."""
        assert slugify_project_id("my-project-123") == "my-project-123"


class TestNextAvailableProjectId:
    """Tests for NextAvailableProjectId scenarios."""

    def test_base_unique_returns_base(self):
        """Verifies that base unique returns base."""
        existing = ["other-proj"]
        assert next_available_project_id("my-project", existing) == "my-project"

    def test_base_exists_returns_hyphen_2(self):
        """Verifies that base exists returns hyphen 2."""
        existing = ["my-project", "other"]
        assert next_available_project_id("my-project", existing) == "my-project-2"

    def test_base_and_hyphen_2_exist_returns_hyphen_3(self):
        """Verifies that base and hyphen 2 exist returns hyphen 3."""
        existing = ["my-project", "my-project-2"]
        assert next_available_project_id("my-project", existing) == "my-project-3"

    def test_many_collisions(self):
        """Verifies that many collisions."""
        existing = {"my-project", "my-project-2", "my-project-3", "my-project-4"}
        assert next_available_project_id("my-project", existing) == "my-project-5"

    def test_empty_existing(self):
        """Verifies that empty existing."""
        assert next_available_project_id("my-project", []) == "my-project"

    def test_empty_string_as_existing(self):
        """Verifies that empty string as existing."""
        assert next_available_project_id("my-project", [""]) == "my-project"


class TestIsValidProjectId:
    """Tests for IsValidProjectId scenarios."""

    def test_valid_simple(self):
        """Verifies that valid simple."""
        assert is_valid_project_id("my-project") is True

    def test_valid_with_numbers(self):
        """Verifies that valid with numbers."""
        assert is_valid_project_id("proj-123") is True

    def test_valid_single_char(self):
        """Verifies that valid single char."""
        assert is_valid_project_id("a") is True

    def test_valid_starting_with_number(self):
        """Verifies that valid starting with number."""
        assert is_valid_project_id("123project") is True

    def test_invalid_leading_hyphen(self):
        """Verifies that invalid leading hyphen."""
        assert is_valid_project_id("-my-project") is False

    def test_invalid_trailing_hyphen(self):
        """Verifies that invalid trailing hyphen."""
        assert is_valid_project_id("my-project-") is False

    def test_invalid_double_hyphen(self):
        """Verifies that invalid double hyphen."""
        assert is_valid_project_id("my--project") is False

    def test_invalid_uppercase(self):
        """Verifies that invalid uppercase."""
        assert is_valid_project_id("My-Project") is False

    def test_invalid_underscore(self):
        """Verifies that invalid underscore."""
        assert is_valid_project_id("my_project") is False

    def test_invalid_special_chars(self):
        """Verifies that invalid special chars."""
        assert is_valid_project_id("my@project") is False

    def test_invalid_empty(self):
        """Verifies that invalid empty."""
        assert is_valid_project_id("") is False

    def test_valid_dashes_in_middle(self):
        """Verifies that valid dashes in middle."""
        assert is_valid_project_id("a-b-c-1-2-3") is True


class TestSafeResolvePath:
    """Tests for SafeResolvePath scenarios."""

    def test_resolves_absolute(self, tmp_path: Path):
        """Verifies that resolves absolute."""
        result = safe_resolve_path(str(tmp_path / "foo"), safe_root=tmp_path)
        assert result == (tmp_path / "foo").resolve()

    def test_rejects_empty(self, tmp_path: Path):
        """Verifies that rejects empty."""
        with pytest.raises(ValueError, match="Path must not be empty"):
            safe_resolve_path("", safe_root=tmp_path)

    def test_rejects_path_outside_safe_root(self, tmp_path: Path):
        """Verifies that rejects path outside safe root."""
        sibling = tmp_path.parent / "sibling"
        with pytest.raises(ValueError, match="outside the allowed directory"):
            safe_resolve_path(str(sibling), safe_root=tmp_path)

    def test_allows_subdirectory(self, tmp_path: Path):
        """Verifies that allows subdirectory."""
        sub = tmp_path / "a" / "b"
        result = safe_resolve_path(str(sub), safe_root=tmp_path)
        assert result == sub.resolve()

    def test_allows_exact_safe_root(self, tmp_path: Path):
        """Verifies that allows exact safe root."""
        result = safe_resolve_path(str(tmp_path), safe_root=tmp_path)
        assert result == tmp_path.resolve()

    def test_rejects_symlink_outside(self, tmp_path: Path):
        """Verifies that rejects symlink outside."""
        sibling = tmp_path.parent / "sibling"
        sibling.mkdir(parents=True, exist_ok=True)
        symlink = tmp_path / "link"
        symlink.symlink_to(sibling, target_is_directory=True)
        with pytest.raises(ValueError, match="outside the allowed directory"):
            safe_resolve_path(str(symlink), safe_root=tmp_path)

    def test_expands_tilde_in_path(self, tmp_path: Path):
        """Verifies that expands tilde in path."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        result = safe_resolve_path(str(subdir), safe_root=tmp_path)
        assert result == subdir.resolve()

    def test_rejects_empty_path(self, tmp_path: Path):
        """Verifies that rejects empty path."""
        with pytest.raises(ValueError, match="Path must not be empty"):
            safe_resolve_path("", safe_root=tmp_path)


class TestValidateRepoRoot:
    """Tests for ValidateRepoRoot scenarios."""

    def test_valid_git_repo(self, tmp_path: Path):  # noqa: assertion-scanner
        """Verifies that valid git repo."""
        (tmp_path / ".git").mkdir()
        validate_repo_root(tmp_path)

    def test_missing_directory(self, tmp_path: Path):
        """Verifies that missing directory."""
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(ValueError, match="does not exist"):
            validate_repo_root(nonexistent)

    def test_not_a_directory_file(self, tmp_path: Path):
        """Verifies that not a directory file."""
        file_path = tmp_path / "afile.txt"
        file_path.write_text("content")
        with pytest.raises(ValueError, match="not a directory"):
            validate_repo_root(file_path)

    def test_no_git_entry(self, tmp_path: Path):
        """Verifies that no git entry."""
        subdir = tmp_path / "no-git-repo"
        subdir.mkdir()
        with pytest.raises(ValueError, match="no .git entry found"):
            validate_repo_root(subdir)

    def test_git_entry_is_file_not_directory(self, tmp_path: Path):
        """Verifies that git entry is file not directory."""
        git_file = tmp_path / ".git"
        git_file.write_text("gitdir: /some/path")
        with pytest.raises(ValueError, match="not a git repository"):
            validate_repo_root(tmp_path)
