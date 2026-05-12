"""Guard test for the CR-00047 coverage-gate config.

Pins the parsed values that the coverage gates depend on so they can't
silently drift away:

* ``[tool.coverage.report] fail_under`` is the raised floor (> the old 46),
* ``[tool.coverage.run] relative_files`` is enabled,
* ``diff-cover`` is in the dev dependency group,
* the ``Makefile`` has a ``diff-coverage`` target.

These are real assertions on the actual parsed values — not ``is not None``
placeholders — so the ``assertions`` QV gate has something concrete to check.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

# Floor chosen in CR-00047 from the S01 measurement (just below the lower of
# the unit / integration+dashboard branch-coverage slices, with headroom).
# Ratchet this UP over time as coverage improves — never down.
COVERAGE_FAIL_UNDER = 50

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_MAKEFILE = _REPO_ROOT / "Makefile"


def _pyproject() -> dict:
    return tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))


def test_coverage_fail_under_is_the_raised_floor() -> None:
    fail_under = _pyproject()["tool"]["coverage"]["report"]["fail_under"]
    assert fail_under == COVERAGE_FAIL_UNDER
    # The whole point of CR-00047 is that the floor is no longer the old 46.
    assert fail_under > 46
    assert fail_under < 100


def test_coverage_run_uses_relative_files() -> None:
    run_cfg = _pyproject()["tool"]["coverage"]["run"]
    assert run_cfg["relative_files"] is True


def test_diff_cover_is_a_dev_dependency() -> None:
    dev_group = _pyproject()["dependency-groups"]["dev"]
    assert any(spec.split(">=")[0].split("==")[0].strip() == "diff-cover" for spec in dev_group)


def test_makefile_has_diff_coverage_target() -> None:
    makefile = _MAKEFILE.read_text(encoding="utf-8")
    # The target is declared exactly once...
    assert makefile.count("\ndiff-coverage:") == 1
    # ...and its recipe actually runs diff-cover against origin/main, not an
    # empty .PHONY stub (regression guard against the allure-* targets' fate).
    recipe = makefile.split("\ndiff-coverage:", 1)[1].split("\n\n", 1)[0]
    assert "diff-cover " in recipe
    assert "--compare-branch=origin/main" in recipe
    assert "--fail-under=90" in recipe
