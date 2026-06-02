"""Unit tests for lint scripts under scripts/check_*.py.

These tests use tmp_path to exercise the lint scripts without touching
the real repository tree.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ----------------------------------------------------------------------
# check_downgrade_minus1.py
# ----------------------------------------------------------------------


def test_downgrade_minus1_catches_double_quote_violation(tmp_path: Path) -> None:
    """Script exits 1 when a test file calls downgrade(cfg, \"-1\")."""
    test_file = tmp_path / "test_sample.py"
    test_file.write_text('from alembic import command\n\ncommand.downgrade(cfg, "-1")\n')

    result = subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parent.parent.parent
                / "scripts"
                / "check_downgrade_minus1.py"
            ),
            "--tests-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (
        f"Expected exit 1, got {result.returncode}. stderr={result.stderr}"
    )


def test_downgrade_minus1_catches_single_quote_violation(tmp_path: Path) -> None:
    """Script exits 1 when a test file calls downgrade(cfg, '-1')."""
    test_file = tmp_path / "test_single.py"
    test_file.write_text("from alembic import command\n\ncommand.downgrade(cfg, '-1')\n")

    result = subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parent.parent.parent
                / "scripts"
                / "check_downgrade_minus1.py"
            ),
            "--tests-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (
        f"Expected exit 1, got {result.returncode}. stderr={result.stderr}"
    )


def test_downgrade_minus1_clean_file_exits_zero(tmp_path: Path) -> None:
    """Script exits 0 when the test tree contains no downgrade('-1') calls."""
    test_file = tmp_path / "test_clean.py"
    test_file.write_text('from alembic import command\n\ncommand.downgrade(cfg, "abc123")\n')

    result = subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parent.parent.parent
                / "scripts"
                / "check_downgrade_minus1.py"
            ),
            "--tests-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}. stderr={result.stderr}"
    )


def test_downgrade_minus1_specific_revision_exits_zero(tmp_path: Path) -> None:
    """Script exits 0 when downgrade is called with a specific revision, not -1."""
    test_file = tmp_path / "test_specific.py"
    test_file.write_text('from alembic import command\n\ncommand.downgrade(cfg, "b4c8opus48rt")\n')

    result = subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parent.parent.parent
                / "scripts"
                / "check_downgrade_minus1.py"
            ),
            "--tests-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}. stderr={result.stderr}"
    )


# ----------------------------------------------------------------------
# check_pending_down_revision.py
# ----------------------------------------------------------------------
# Unit-test the pure predicate: check_file(path) -> list[tuple[int, str]]
# We import it directly (not via subprocess) so the test fails immediately
# if the module/symbol does not exist yet (RED evidence).


def test_pending_down_revision_catches_hardcoded_hash(tmp_path: Path) -> None:
    """check_file flags down_revision = 'abc123' (hardcoded hash)."""
    from scripts.check_pending_down_revision import check_file  # noqa: F401

    fake_migration = tmp_path / "test_hardcoded.py"
    fake_migration.write_text('down_revision = "b4c8opus48rt"\n')
    violations = check_file(fake_migration)
    assert violations, "Expected non-empty violations for hardcoded down_revision hash"
    assert violations[0][0] == 1  # line 1


def test_pending_down_revision_allows_pending_sentinel(tmp_path: Path) -> None:
    """check_file returns [] for down_revision = "PENDING" (correct sentinel)."""
    from scripts.check_pending_down_revision import check_file  # noqa: F401

    fake_migration = tmp_path / "test_pending.py"
    fake_migration.write_text('down_revision = "PENDING"\n')
    violations = check_file(fake_migration)
    assert violations == [], f"Expected no violations for 'PENDING' sentinel, got {violations}"


def test_pending_down_revision_allows_none(tmp_path: Path) -> None:
    """check_file returns [] for down_revision = None (baseline migration)."""
    from scripts.check_pending_down_revision import check_file  # noqa: F401

    fake_migration = tmp_path / "test_none.py"
    fake_migration.write_text("down_revision = None\n")
    violations = check_file(fake_migration)
    assert violations == [], f"Expected no violations for None, got {violations}"


def test_pending_down_revision_allows_merge_tuple_with_pending(tmp_path: Path) -> None:
    """check_file returns [] for down_revision = ("PENDING", "abc123") (merge migration)."""
    from scripts.check_pending_down_revision import check_file  # noqa: F401

    fake_migration = tmp_path / "test_merge_tuple.py"
    fake_migration.write_text('down_revision = ("PENDING", "abc123")\n')
    violations = check_file(fake_migration)
    assert violations == [], f"Expected no violations for merge tuple form, got {violations}"


def test_pending_down_revision_catches_annotated_hardcoded_hash(tmp_path: Path) -> None:
    """check_file flags down_revision: str | None = 'abc123' (type annotation + hardcoded hash)."""
    from scripts.check_pending_down_revision import check_file  # noqa: F401

    fake_migration = tmp_path / "test_annotated.py"
    fake_migration.write_text("down_revision: str | None = 'b4c8opus48rt'\n")
    violations = check_file(fake_migration)
    assert violations, (
        f"Expected non-empty violations for annotated hardcoded hash, got {violations}"
    )
    assert violations[0][0] == 1
