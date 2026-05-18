"""Pins the quarantine workflow config so future edits don't silently drift.

Written RED-first for CR-00061 (P2-CR-C): fails before the marker/addopts/
make targets/aggregator script exist; passes after S01 lands them.
"""

import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_quarantine_marker_registered():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    markers = data["tool"]["pytest"]["ini_options"]["markers"]
    assert any(m.startswith("quarantine:") for m in markers), (
        "`quarantine: ...` marker must be registered in [tool.pytest.ini_options].markers"
    )


def test_addopts_deselects_quarantine():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    addopts = data["tool"]["pytest"]["ini_options"]["addopts"]
    assert "not browser and not quarantine" in addopts, (
        f"addopts must filter out quarantine via 'not browser and not quarantine'; got: {addopts!r}"
    )
    assert "--strict-markers" in addopts, "addopts must keep --strict-markers"
    # Defensive: the old standalone `not browser` filter must be replaced, not duplicated
    assert addopts.count("-m ") == 1, (
        f"addopts must contain exactly one -m filter; got: {addopts!r}"
    )


def test_pytest_rerunfailures_installed():
    import pytest_rerunfailures

    assert hasattr(pytest_rerunfailures, "__version__") or True


def test_makefile_exposes_quarantine_and_flake_detect_targets():
    for target in ("test-quarantine", "test-flake-detect"):
        result = subprocess.run(
            ["make", "-n", target],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert "No rule to make target" not in result.stderr, (
            f"make -n {target}: missing — CR-00061 must land both recipes\n{result.stderr}"
        )
        assert result.returncode == 0, f"make -n {target}: parse failed\n{result.stderr}"


def test_flake_detect_aggregator_is_valid_python():
    script = REPO_ROOT / "scripts" / "flake_detect_aggregate.py"
    assert script.exists(), "scripts/flake_detect_aggregate.py missing"
    # Validate it parses
    import ast

    ast.parse(script.read_text())
    # Stdlib-only check (no third-party imports)
    src = script.read_text()
    for forbidden in ("import pytest", "import requests", "import httpx", "from pytest"):
        assert forbidden not in src, f"aggregator must be stdlib-only; found {forbidden!r}"
