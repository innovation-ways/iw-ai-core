"""Unit tests for the E2E seed fixture discovery/runner mechanism.

These are pure filesystem tests — no DB required. They prove the runner:
- finds fixtures in both active/ and archive/ directories
- orders them lexically (so 001_ loads before 002_)
- skips files starting with '_' (so __init__.py doesn't explode)
- raises a clear error when a fixture has no seed() callable
- calls each fixture's seed(db) with the provided session
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from scripts.e2e_seed import _discover_fixture_files, _run_fixture

if TYPE_CHECKING:
    from pathlib import Path


def _write_fixture(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_discover_returns_empty_when_no_ai_dev_dir(tmp_path: Path) -> None:
    """Verifies that discover returns empty when no ai dev dir."""
    assert _discover_fixture_files(tmp_path) == []


def test_discover_finds_active_and_archive_fixtures(tmp_path: Path) -> None:
    """Verifies that discover finds active and archive fixtures."""
    active_fx = tmp_path / "ai-dev" / "active" / "F-00099" / "e2e_fixtures" / "001_a.py"
    archive_fx = tmp_path / "ai-dev" / "archive" / "F-00050" / "e2e_fixtures" / "001_b.py"
    _write_fixture(active_fx, "def seed(db): pass\n")
    _write_fixture(archive_fx, "def seed(db): pass\n")

    found = _discover_fixture_files(tmp_path)
    assert active_fx in found
    assert archive_fx in found


def test_discover_orders_fixtures_lexically(tmp_path: Path) -> None:
    """Verifies that discover orders fixtures lexically."""
    base = tmp_path / "ai-dev" / "active" / "F-00099" / "e2e_fixtures"
    _write_fixture(base / "003_c.py", "def seed(db): pass\n")
    _write_fixture(base / "001_a.py", "def seed(db): pass\n")
    _write_fixture(base / "002_b.py", "def seed(db): pass\n")

    found = _discover_fixture_files(tmp_path)
    names = [f.name for f in found]
    assert names == ["001_a.py", "002_b.py", "003_c.py"]


def test_discover_skips_underscore_prefixed_files(tmp_path: Path) -> None:
    """Verifies that discover skips underscore prefixed files."""
    base = tmp_path / "ai-dev" / "active" / "F-00099" / "e2e_fixtures"
    _write_fixture(base / "__init__.py", "")
    _write_fixture(base / "_private.py", "def seed(db): pass\n")
    _write_fixture(base / "001_real.py", "def seed(db): pass\n")

    found = _discover_fixture_files(tmp_path)
    names = [f.name for f in found]
    assert names == ["001_real.py"]


def test_run_fixture_invokes_seed_with_db(tmp_path: Path) -> None:
    """Verifies that run fixture invokes seed with db."""
    fx = tmp_path / "ai-dev" / "active" / "F-00099" / "e2e_fixtures" / "001_test.py"
    _write_fixture(
        fx,
        "called = []\ndef seed(db):\n    called.append(db)\n    db.sentinel = 'ran'\n",
    )

    stub_db: Any = SimpleNamespace(sentinel=None)
    _run_fixture(fx, stub_db)
    assert stub_db.sentinel == "ran"


def test_run_fixture_rejects_module_without_seed(tmp_path: Path) -> None:
    """Verifies that run fixture rejects module without seed."""
    fx = tmp_path / "ai-dev" / "active" / "F-00099" / "e2e_fixtures" / "001_broken.py"
    _write_fixture(fx, "# no seed function here\n")

    with pytest.raises(RuntimeError, match="no callable seed"):
        _run_fixture(fx, SimpleNamespace())


def test_run_fixture_propagates_seed_errors(tmp_path: Path) -> None:
    """Fixtures that raise must propagate — silent partial seeds reintroduce
    the empty-DB QvBrowser failure class this mechanism was built to prevent.
    """
    fx = tmp_path / "ai-dev" / "active" / "F-00099" / "e2e_fixtures" / "001_raises.py"
    _write_fixture(fx, "def seed(db):\n    raise ValueError('boom')\n")

    with pytest.raises(ValueError, match="boom"):
        _run_fixture(fx, SimpleNamespace())
