"""Unit tests for backfill_functional_doc.py --load-db flag and --force interaction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_FUNCTIONAL_CONTENT = "# F-00001 Functional Design\n\n## Why\nTest content."


@pytest.fixture
def mock_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a fake project root with ai-dev/active/<ID>/ directories."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    return repo_root


class TestBackfillLoadDb:
    """Parameterised cases for --load-db behaviour."""

    def test_load_db_updates_db_columns(
        self,
        mock_project_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--load-db path: opencode produces file -> DB UPDATE occurs, columns set."""
        item_id = "F-00001"
        item_dir = mock_project_root / "ai-dev" / "active" / item_id
        item_dir.mkdir(parents=True)
        output_path = item_dir / f"{item_id}_Functional.md"

        monkeypatch.setattr("sys.argv", ["backfill", item_id, "--load-db"])

        with (
            patch("subprocess.run") as mock_run,
            patch("scripts.backfill_functional_doc.find_project_root") as mock_find,
            patch("scripts.backfill_functional_doc.SessionLocal") as mock_session_cls,
        ):

            def fake_run(*args: object, **kwargs: object) -> MagicMock:
                output_path.write_text(_FUNCTIONAL_CONTENT, encoding="utf-8")
                result = MagicMock()
                result.returncode = 0
                return result

            mock_run.side_effect = fake_run
            mock_find.return_value = ("test-proj", mock_project_root)

            mock_item = MagicMock()
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=None)
            mock_session.get.return_value = mock_item

            from scripts.backfill_functional_doc import main

            result = main()

            assert result == 0
            assert mock_session.get.call_count == 2
            mock_session.commit.assert_called_once()
            assert mock_item.functional_doc_path == (
                f"ai-dev/active/{item_id}/{item_id}_Functional.md"
            )
            assert mock_item.functional_doc_content is not None

    def test_load_db_missing_item_exits_4(
        self,
        mock_project_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--load-db with missing item -> exit 4, no DB write."""
        monkeypatch.setattr("sys.argv", ["backfill", "F-99999", "--load-db"])

        with (
            patch("subprocess.run") as mock_run,
            patch("scripts.backfill_functional_doc.find_project_root") as mock_find,
            patch("scripts.backfill_functional_doc.SessionLocal") as mock_session_cls,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            mock_find.return_value = ("test-proj", mock_project_root)

            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=None)
            mock_session.get.return_value = None

            from scripts.backfill_functional_doc import main

            result = main()

            assert result == 4
            mock_session.commit.assert_not_called()

    def test_load_db_sqlalchemy_error_exits_7(
        self,
        mock_project_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--load-db with SQLAlchemy exception -> exit 7."""
        item_id = "F-00001"
        item_dir = mock_project_root / "ai-dev" / "active" / item_id
        item_dir.mkdir(parents=True)
        output_path = item_dir / f"{item_id}_Functional.md"

        monkeypatch.setattr("sys.argv", ["backfill", item_id, "--load-db"])

        with (
            patch("subprocess.run") as mock_run,
            patch("scripts.backfill_functional_doc.find_project_root") as mock_find,
            patch("scripts.backfill_functional_doc.SessionLocal") as mock_session_cls,
        ):

            def fake_run(*args: object, **kwargs: object) -> MagicMock:
                output_path.write_text(_FUNCTIONAL_CONTENT, encoding="utf-8")
                result = MagicMock()
                result.returncode = 0
                return result

            mock_run.side_effect = fake_run
            mock_find.return_value = ("test-proj", mock_project_root)

            mock_item = MagicMock()
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=None)
            mock_session.get.return_value = mock_item

            from sqlalchemy.exc import SQLAlchemyError

            mock_session.commit.side_effect = SQLAlchemyError("DB error")

            from scripts.backfill_functional_doc import main

            result = main()

            assert result == 7

    def test_default_no_load_db_commits_only_once(
        self,
        mock_project_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Default (no --load-db): no DB UPDATE commit after opencode succeeds."""
        item_id = "F-00001"
        item_dir = mock_project_root / "ai-dev" / "active" / item_id
        item_dir.mkdir(parents=True)
        output_path = item_dir / f"{item_id}_Functional.md"

        monkeypatch.setattr("sys.argv", ["backfill", item_id])

        with (
            patch("subprocess.run") as mock_run,
            patch("scripts.backfill_functional_doc.find_project_root") as mock_find,
            patch("scripts.backfill_functional_doc.SessionLocal") as mock_session_cls,
        ):

            def fake_run(*args: object, **kwargs: object) -> MagicMock:
                output_path.write_text(_FUNCTIONAL_CONTENT, encoding="utf-8")
                result = MagicMock()
                result.returncode = 0
                return result

            mock_run.side_effect = fake_run
            mock_find.return_value = ("test-proj", mock_project_root)

            mock_item = MagicMock()
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=None)
            mock_session.get.return_value = mock_item

            from scripts.backfill_functional_doc import main

            result = main()

            assert result == 0
            commit_count = mock_session.commit.call_count
            assert commit_count == 0, f"Expected no commits on default path, got {commit_count}"

    def test_opencode_failure_returns_opencode_exit_code(
        self,
        mock_project_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """opencode exits non-zero -> script exits with that code; DB not touched."""
        item_id = "F-00001"
        item_dir = mock_project_root / "ai-dev" / "active" / item_id
        item_dir.mkdir(parents=True)

        monkeypatch.setattr("sys.argv", ["backfill", item_id, "--load-db"])

        with (
            patch("subprocess.run") as mock_run,
            patch("scripts.backfill_functional_doc.find_project_root") as mock_find,
            patch("scripts.backfill_functional_doc.SessionLocal") as mock_session_cls,
        ):
            mock_run.return_value = MagicMock(returncode=42)
            mock_find.return_value = ("test-proj", mock_project_root)

            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=None)
            mock_session.get.return_value = MagicMock()

            from scripts.backfill_functional_doc import main

            result = main()

            assert result == 42

    def test_force_and_load_db_compose_correctly(
        self,
        mock_project_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--force + --load-db: existing file is overwritten, DB UPDATE follows."""
        item_id = "F-00001"
        item_dir = mock_project_root / "ai-dev" / "active" / item_id
        item_dir.mkdir(parents=True)
        output_path = item_dir / f"{item_id}_Functional.md"
        output_path.write_text("# Old content", encoding="utf-8")

        monkeypatch.setattr("sys.argv", ["backfill", item_id, "--force", "--load-db"])

        with (
            patch("subprocess.run") as mock_run,
            patch("scripts.backfill_functional_doc.find_project_root") as mock_find,
            patch("scripts.backfill_functional_doc.SessionLocal") as mock_session_cls,
        ):

            def fake_run(*args: object, **kwargs: object) -> MagicMock:
                output_path.write_text(_FUNCTIONAL_CONTENT, encoding="utf-8")
                result = MagicMock()
                result.returncode = 0
                return result

            mock_run.side_effect = fake_run
            mock_find.return_value = ("test-proj", mock_project_root)

            mock_item = MagicMock()
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=None)
            mock_session.get.return_value = mock_item

            from scripts.backfill_functional_doc import main

            result = main()

            assert result == 0
            mock_session.commit.assert_called_once()
            assert output_path.read_text(encoding="utf-8") == _FUNCTIONAL_CONTENT
