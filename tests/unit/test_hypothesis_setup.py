"""Pins the Hypothesis configuration so future edits don't silently drift.

Written RED-first for CR-00060 (P2-CR-B): fails before hypothesis is installed
AND before the properties dir/conftest/marker exist; passes after S01 lands them.
"""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_hypothesis_is_importable():
    """The dev dep must resolve."""
    import hypothesis

    assert hasattr(hypothesis, "__version__"), "hypothesis must have a __version__ attribute"


def test_pyproject_has_hypothesis_config_and_marker():
    """Verifies that pyproject has hypothesis config and marker."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert "hypothesis" in data["tool"], "[tool.hypothesis] block missing"
    assert "database_file" in data["tool"]["hypothesis"]
    markers = data["tool"]["pytest"]["ini_options"]["markers"]
    assert any("properties" in m for m in markers), (
        "`properties` marker must be registered in [tool.pytest.ini_options].markers"
    )


def test_properties_conftest_registers_three_profiles():
    """Verifies that properties conftest registers three profiles."""
    conftest = REPO_ROOT / "tests" / "unit" / "properties" / "conftest.py"
    assert conftest.exists(), "tests/unit/properties/conftest.py missing"
    text = conftest.read_text()
    for profile in ("ci", "dev", "deep"):
        # Profile is registered via settings.register_profile(profile, ...)
        # Check that the profile name appears inside a register_profile call
        assert f'register_profile(\n    "{profile}",' in text, (
            f"profile {profile!r} must be registered in tests/unit/properties/conftest.py"
        )
