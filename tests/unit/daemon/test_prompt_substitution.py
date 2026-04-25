"""Unit tests for worktree placeholder substitution in step prompts.

Tests:
  - test_substitutes_all_known_placeholders
  - test_unknown_placeholder_left_alone
  - test_legacy_mode_with_no_placeholders_unchanged
  - test_legacy_mode_with_placeholders_raises_clear_error
"""

from __future__ import annotations

import pytest

from orch.daemon.batch_manager import (
    UnresolvedWorktreePlaceholderError,
    substitute_worktree_placeholders,
)


class TestSubstituteWorktreePlaceholders:
    """Tests for the substitute_worktree_placeholders function."""

    def test_substitutes_all_known_placeholders(self) -> None:
        """All five known placeholders are replaced when values are present."""
        worktree_info = {
            "worktree_compose_path": "/home/user/project/.worktrees/F-00001/.iw/docker-compose.yml",
            "worktree_db_port": 54321,
            "worktree_app_port": 29900,
            "worktree_path": "/home/user/project/.worktrees/F-00001",
            "batch_item_id": 42,
            "project_name": "iw-ai-core",
        }

        prompt = (
            "Connect to the DB at localhost:${WORKTREE_DB_PORT} "
            "and the app at localhost:${WORKTREE_APP_PORT}. "
            "Worktree path: ${WORKTREE_PATH}. "
            "Batch item: ${BATCH_ITEM_ID}. "
            "Project: ${PROJECT_NAME}."
        )

        result = substitute_worktree_placeholders(prompt, worktree_info)

        assert result == (
            "Connect to the DB at localhost:54321 "
            "and the app at localhost:29900. "
            "Worktree path: /home/user/project/.worktrees/F-00001. "
            "Batch item: 42. "
            "Project: iw-ai-core."
        )

    def test_unknown_placeholder_left_alone(self) -> None:
        """Placeholders not in the known set are preserved verbatim."""
        worktree_info = {
            "worktree_compose_path": "/path/to/compose.yml",
            "worktree_db_port": 54321,
            "worktree_app_port": 29900,
            "worktree_path": "/path/to/worktree",
            "batch_item_id": 1,
            "project_name": "test-proj",
        }

        prompt = "Use ${UNKNOWN_VAR} and also ${OTHER_PLACEHOLDER} here."

        result = substitute_worktree_placeholders(prompt, worktree_info)

        assert result == prompt

    def test_legacy_mode_with_no_placeholders_unchanged(self) -> None:
        """Legacy-mode prompts with no placeholders are returned as-is."""
        worktree_info = {
            "worktree_path": "/path/to/legacy/worktree",
        }

        prompt = "This is a legacy prompt without any placeholders."

        result = substitute_worktree_placeholders(prompt, worktree_info)

        assert result == prompt

    def test_legacy_mode_with_worktree_placeholder_raises_clear_error(self) -> None:
        """Legacy-mode prompts with ${WORKTREE_*} raise UnresolvedWorktreePlaceholderError."""
        worktree_info = {
            "worktree_path": "/path/to/legacy/worktree",
        }

        prompt = "Connect to the per-worktree DB at localhost:${WORKTREE_DB_PORT}"

        with pytest.raises(UnresolvedWorktreePlaceholderError) as exc_info:
            substitute_worktree_placeholders(prompt, worktree_info)

        assert "WORKTREE_DB_PORT" in str(exc_info.value)
        assert "legacy mode" in str(exc_info.value)

    def test_non_worktree_placeholder_in_legacy_mode_unchanged(self) -> None:
        """Non-WORKTREE placeholders like ${BATCH_ITEM_ID} are left alone even in legacy mode."""
        worktree_info = {
            "worktree_path": "/path/to/legacy/worktree",
        }

        prompt = "Batch item is ${BATCH_ITEM_ID} and project is ${PROJECT_NAME}"

        result = substitute_worktree_placeholders(prompt, worktree_info)

        assert result == prompt

    def test_batch_item_id_and_project_name_work_in_per_worktree_mode(self) -> None:
        """${BATCH_ITEM_ID} and ${PROJECT_NAME} resolve correctly in per-worktree mode."""
        worktree_info = {
            "worktree_compose_path": "/path/to/compose.yml",
            "worktree_db_port": 54321,
            "worktree_app_port": 29900,
            "worktree_path": "/path/to/worktree",
            "batch_item_id": 99,
            "project_name": "my-project",
        }

        prompt = "Batch: ${BATCH_ITEM_ID}, Project: ${PROJECT_NAME}"

        result = substitute_worktree_placeholders(prompt, worktree_info)

        assert result == "Batch: 99, Project: my-project"

    def test_empty_prompt_unchanged(self) -> None:
        """Empty prompt is returned unchanged."""
        worktree_info = {
            "worktree_compose_path": "/path/to/compose.yml",
            "worktree_db_port": 54321,
            "worktree_app_port": 29900,
            "worktree_path": "/path/to/worktree",
            "batch_item_id": 1,
            "project_name": "test",
        }

        result = substitute_worktree_placeholders("", worktree_info)

        assert result == ""

    def test_prompt_with_no_placeholders_unchanged(self) -> None:
        """Prompt without any placeholders is returned unchanged."""
        worktree_info = {
            "worktree_compose_path": "/path/to/compose.yml",
            "worktree_db_port": 54321,
            "worktree_app_port": 29900,
            "worktree_path": "/path/to/worktree",
            "batch_item_id": 1,
            "project_name": "test",
        }

        prompt = "This is a regular prompt with no placeholders."

        result = substitute_worktree_placeholders(prompt, worktree_info)

        assert result == prompt

    def test_substitution_handles_repeated_placeholder_in_same_prompt(self) -> None:
        """Same placeholder appearing multiple times is replaced each time."""
        worktree_info = {
            "worktree_compose_path": "/path/to/compose.yml",
            "worktree_db_port": 54321,
            "worktree_app_port": 29900,
            "worktree_path": "/path/to/worktree",
            "batch_item_id": 42,
            "project_name": "my-project",
        }

        prompt = (
            "DB port is ${WORKTREE_DB_PORT} and again ${WORKTREE_DB_PORT}. "
            "Batch item: ${BATCH_ITEM_ID}. "
            "Also: ${BATCH_ITEM_ID}."
        )

        result = substitute_worktree_placeholders(prompt, worktree_info)

        assert result.count("54321") == 2
        assert result.count("42") == 2
