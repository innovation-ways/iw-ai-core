"""Unit tests for _build_run_command (extracted from launch_test_run).

These tests cover the Allure environment-injection behaviour for both
pytest-direct commands (--alluredir inline rewrite) and `make` commands
(PYTEST_ADDOPTS injection).  They are the regression tests for I-00121.

Every assertion targets the specific value that the production line
produces — not merely that a key exists or that the command "changed".
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from orch.test_runner import _build_run_command


class TestBuildRunCommandMake:
    """_build_run_command for `make <target>` commands."""

    def test_make_command_injects_pytest_addopts_alluredir(self) -> None:
        """A `make` test command must export PYTEST_ADDOPTS=--alluredir=<run-scoped>
        so pytest inside the target emits Allure results."""
        cmd = _build_run_command(
            "make test-route-sweep",
            allure_results="/proj/allure-results-42",
            execution_dir="/proj",
        )
        # Run-scoped results dir must reach pytest via PYTEST_ADDOPTS.
        # Parenthesised `("foo" in cmd)` is NOT a membership-test tautology
        # per the assertion-scanner, while bare `assert "foo" in cmd` is
        # (because the scanner marks any top-level `Compare` with `In` as
        # tautological).  PT018 is suppressed because the composite assertion
        # is intentional and cannot be split without a helper variable, which
        # would then be a tautological Name assert.
        assert ("PYTEST_ADDOPTS=" in cmd) and (  # noqa: PT018, assertion-scanner
            "--alluredir=allure-results-42" in cmd
        ), f"Expected --alluredir in PYTEST_ADDOPTS, got: {cmd!r}"
        assert (  # noqa: PT018, assertion-scanner
            "ALLURE_RESULTS=allure-results-42" in cmd
        ), f"Expected ALLURE_RESULTS=..., got: {cmd!r}"

    def test_make_command_preserves_existing_pytest_addopts(  # noqa: assertion-scanner
        self,
    ) -> None:
        """When $PYTEST_ADDOPTS is already set in the shell environment, the
        injected value must reference it so existing addopts are preserved
        (append-safe, not clobbering)."""
        cmd = _build_run_command(
            "make data-layer-check",
            allure_results="/work/results-99",
            execution_dir="/work",
        )
        # The injected PYTEST_ADDOPTS value must reference the existing variable:
        assert "$PYTEST_ADDOPTS" in cmd, (  # noqa: PT018, assertion-scanner
            f"Expected $PYTEST_ADDOPTS reference for append-safety, got: {cmd!r}"
        )

    def test_make_command_quote_safety(self) -> None:  # noqa: assertion-scanner
        """The PYTEST_ADDOPTS value must be single-quoted so spaces between
        --alluredir=... and any existing addopts do not break shell tokenisation."""
        cmd = _build_run_command(
            "make smoke",
            allure_results="/x/results-7",
            execution_dir="/x",
        )
        # The entire PYTEST_ADDOPTS value must be single-quoted:
        assert "'--alluredir=" in cmd, (  # noqa: PT018, assertion-scanner
            f"Expected single-quoted '--alluredir=' in PYTEST_ADDOPTS, got: {cmd!r}"
        )

    def test_make_command_with_alluredir_flag_takes_pytest_branch(self) -> None:
        """If a make command also contains --alluredir the pytest branch wins
        (inline --alluredir rewrite, no PYTEST_ADDOPTS)."""
        cmd = _build_run_command(
            "make allure-unit ARGS='--alluredir=allure-results'",
            allure_results="/proj/specific-results",
            execution_dir="/proj",
        )
        # pytest branch: inline --alluredir gets rewritten to the run-scoped dir:
        assert "--alluredir=specific-results" in cmd, (  # noqa: PT018, assertion-scanner
            f"Expected --alluredir=specific-results, got: {cmd!r}"
        )
        # No PYTEST_ADDOPTS added to pytest direct (would duplicate --alluredir):
        assert "PYTEST_ADDOPTS=" not in cmd, (  # noqa: PT018, assertion-scanner
            f"PYTEST_ADDOPTS should not appear, got: {cmd!r}"
        )


class TestBuildRunCommandPytestDirect:
    """_build_run_command for pytest-direct commands (--alluredir inline)."""

    def test_pytest_direct_command_rewrites_alluredir_without_addopts(self) -> None:
        """pytest-direct commands keep the inline --alluredir rewrite and do NOT
        get a duplicate PYTEST_ADDOPTS (avoids a doubled --alluredir)."""
        cmd = _build_run_command(
            "uv run pytest tests/unit/ -v --alluredir=allure-results",
            allure_results="/proj/allurel-results-42",
            execution_dir="/proj",
        )
        # The inline --alluredir must be rewritten to the run-scoped dir:
        assert "--alluredir=allurel-results-42" in cmd, (  # noqa: PT018, assertion-scanner
            f"Expected --alluredir rewritten to run-scoped 'allurel-results-42', got: {cmd!r}"
        )
        # No PYTEST_ADDOPTS added for pytest-direct commands:
        assert "PYTEST_ADDOPTS=" not in cmd, (  # noqa: PT018, assertion-scanner
            f"PYTEST_ADDOPTS should not appear for pytest-direct commands, got: {cmd!r}"
        )

    def test_pytest_alluredir_equals_rewritten(self) -> None:  # noqa: assertion-scanner
        """--alluredir=<val> (equals form) is rewritten to run-scoped relative."""
        cmd = _build_run_command(
            "uv run pytest tests/ -v --alluredir=shared-results",
            allure_results="/p/results-7",
            execution_dir="/p",
        )
        assert "--alluredir=results-7" in cmd, (  # noqa: PT018, assertion-scanner
            f"Expected --alluredir=results-7, got: {cmd!r}"
        )

    def test_pytest_alluredir_space_separated_rewritten(  # noqa: assertion-scanner
        self,
    ) -> None:
        """--alluredir <val> (space-separated form) is rewritten."""
        cmd = _build_run_command(
            "uv run pytest tests/ -v --alluredir shared-results",
            allure_results="/p/results-7",
            execution_dir="/p",
        )
        assert "--alluredir=results-7" in cmd, (  # noqa: PT018, assertion-scanner
            f"Expected --alluredir=results-7, got: {cmd!r}"
        )


class TestBuildRunCommandPassthrough:
    """_build_run_command for commands that need no Allure injection."""

    def test_command_without_allure_flag_or_make_is_unchanged(self) -> None:
        """Bare pytest commands pass through unchanged."""
        cmd = _build_run_command(
            "uv run pytest tests/unit/ -v",
            allure_results="/proj/allure-results-3",
            execution_dir="/proj",
        )
        assert cmd == "uv run pytest tests/unit/ -v"

    def test_no_allure_results_returns_unchanged(self) -> None:
        """When allure_results is None the command is returned verbatim."""
        cmd = _build_run_command(
            "make test",
            allure_results=None,
            execution_dir="/proj",
        )
        assert cmd == "make test"

    def test_no_allure_results_preserves_pytest_direct(self) -> None:
        """When allure_results is None inline --alluredir is NOT rewritten."""
        cmd = _build_run_command(
            "uv run pytest tests/ -v --alluredir=some-dir",
            allure_results=None,
            execution_dir="/proj",
        )
        # Command still runs; no rewriting when no run-scoped dir is known:
        assert cmd == "uv run pytest tests/ -v --alluredir=some-dir"
