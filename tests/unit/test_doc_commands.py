"""Unit tests for doc CLI commands (argument parsing, no DB required)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from click.testing import CliRunner

from orch.cli.doc_commands import doc_update

if TYPE_CHECKING:
    from pathlib import Path


class TestDocUpdateMutualExclusion:
    """--content and --content-file are mutually exclusive."""

    def test_both_content_and_content_file_exits_2(self, tmp_path: Path) -> None:
        """Verifies that both content and content file exits 2."""
        runner = CliRunner()
        content_file = tmp_path / "doc.md"
        content_file.write_text("# Doc", encoding="utf-8")

        result = runner.invoke(
            doc_update,
            ["doc1", "--content", "inline content", "--content-file", str(content_file)],
            obj={"project_id": "proj1", "get_session": _make_fake_get_session()},
        )

        assert result.exit_code == 2
        assert "mutually exclusive" in result.stderr


class TestDocUpdateContentSizeLimit:
    """Content exceeding 10 MB is rejected."""

    def test_content_too_large_exits_2(self, tmp_path: Path) -> None:
        """Verifies that content too large exits 2."""
        runner = CliRunner()
        large_file = tmp_path / "large.md"
        large_file.write_text("x" * (10 * 1024 * 1024 + 1), encoding="utf-8")

        result = runner.invoke(
            doc_update,
            ["doc1", "--content-file", str(large_file)],
            obj={"project_id": "proj1", "get_session": _make_fake_get_session()},
        )

        assert result.exit_code == 2
        assert "exceeds maximum size" in result.stderr


class TestDocUpdateHelp:
    """CLI help output is correct."""

    def test_help_shows_all_options(self) -> None:
        """Verifies that help shows all options."""
        runner = CliRunner()
        result = runner.invoke(doc_update, ["--help"])

        assert result.exit_code == 0
        assert "--title" in result.output
        assert "--content" in result.output
        assert "--content-file" in result.output
        assert "--audience" in result.output
        assert "--source-paths" in result.output
        assert "--doc-type" in result.output
        assert "mutually exclusive" in result.output


class _FakeSession:
    """Minimal session stub for argument validation tests."""

    def get(self, model: type, key: str) -> Any:
        """Return get."""
        return None

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def _make_fake_get_session() -> Any:
    """Return a minimal session-like context manager for argument parsing tests."""

    def _get_session() -> _FakeSession:
        return _FakeSession()

    return _get_session
