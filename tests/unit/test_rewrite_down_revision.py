"""Unit tests for rewrite down revision."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "rewrite_down_revision.py"


def _run_script(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(path)],
        capture_output=True,
        text=True,
    )


def test_rewrites_hex_down_revision(tmp_path: Path) -> None:
    """Verifies that rewrites hex down revision."""
    migration_path = tmp_path / "rev_test.py"
    original = '''"""add table"""

revision = "89abcdef1234"
down_revision = "76250ecb2593"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
'''
    migration_path.write_text(original)

    result = _run_script(migration_path)

    assert result.returncode == 0
    assert migration_path.read_text() == original.replace(
        'down_revision = "76250ecb2593"', 'down_revision = "PENDING"'
    )


def test_rewrites_none_down_revision(tmp_path: Path) -> None:
    """Verifies that rewrites none down revision."""
    migration_path = tmp_path / "rev_none.py"
    migration_path.write_text("down_revision = None\n")

    result = _run_script(migration_path)

    assert result.returncode == 0
    assert migration_path.read_text() == 'down_revision = "PENDING"\n'


def test_rewrites_typed_annotation_form(tmp_path: Path) -> None:
    """Verifies that rewrites typed annotation form."""
    migration_path = tmp_path / "rev_typed.py"
    migration_path.write_text('down_revision: str | tuple[str, ...] | None = "abc123ef"\n')

    result = _run_script(migration_path)

    assert result.returncode == 0
    assert migration_path.read_text() == 'down_revision: str | tuple[str, ...] | None = "PENDING"\n'


def test_idempotent_pending(tmp_path: Path) -> None:
    """Verifies that idempotent pending."""
    migration_path = tmp_path / "rev_pending.py"
    original = 'down_revision = "PENDING"\n'
    migration_path.write_text(original)

    result = _run_script(migration_path)

    assert result.returncode == 0
    assert migration_path.read_text() == original


def test_no_down_revision_raises(tmp_path: Path) -> None:
    """Verifies that no down revision raises."""
    migration_path = tmp_path / "no_down_revision.py"
    migration_path.write_text('revision = "abc"\n')

    result = _run_script(migration_path)

    assert result.returncode != 0
    assert f"Error: no down_revision line found in {migration_path}" in result.stderr


def test_missing_file_raises(tmp_path: Path) -> None:
    """Verifies that missing file raises."""
    missing_path = tmp_path / "missing.py"

    result = _run_script(missing_path)

    assert result.returncode != 0
    assert f"Error: file not found: {missing_path}" in result.stderr
