"""Pins the mutmut configuration so future edits don't silently drift away.

Written RED-first for CR-00059 (P2-CR-A): both tests fail before [tool.mutmut]
and the Makefile mutation-* recipes exist, and pass after S01 lands them.
"""

import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_tool_mutmut_block_pins_orch_daemon_target() -> None:
    """[tool.mutmut] must exist with the three expected keys scoped to orch/daemon/."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())

    assert "mutmut" in data["tool"], (
        "[tool.mutmut] block missing — CR-00059 requires it for mutation testing"
    )
    block = data["tool"]["mutmut"]

    assert block["paths_to_mutate"] == "orch/daemon/", (
        "paths_to_mutate must be 'orch/daemon/' "
        f"(spike scope per CR-00059); got {block['paths_to_mutate']!r}"
    )
    assert block["tests_dir"] == "tests/", (
        f"tests_dir must be the single existing directory 'tests/' — "
        f"mutmut 2.5.1 rejects space-joined multi-path strings with FileNotFoundError; "
        f"test-scope narrowing happens in `runner`. Got {block['tests_dir']!r}"
    )
    assert "pytest" in block["runner"], (
        "runner must invoke pytest with -x "
        f"(stop-on-first-fail per mutmut convention); got {block['runner']!r}"
    )
    assert "-x" in block["runner"], (
        "runner must invoke pytest with -x "
        f"(stop-on-first-fail per mutmut convention); got {block['runner']!r}"
    )
    assert "tests/unit/daemon/" in block["runner"], (
        "runner must scope to daemon test dirs "
        "(mutmut runs this verbatim — this is the actual test-scope narrowing); "
        f"got {block['runner']!r}"
    )
    assert "tests/integration/daemon/" in block["runner"], (
        "runner must scope to daemon test dirs "
        "(mutmut runs this verbatim — this is the actual test-scope narrowing); "
        f"got {block['runner']!r}"
    )


def test_makefile_exposes_four_mutation_targets() -> None:
    """All four `mutation-*` targets must parse via `make -n`."""
    for target, extra in [
        ("mutation-check", ["MODULE=orch/daemon/auto_merge.py"]),
        ("mutation-audit", []),
        ("mutation-results", []),
        ("mutation-show", ["ID=1"]),
    ]:
        result = subprocess.run(  # noqa: S603
            ["make", "-n", target, *extra],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert "No rule to make target" not in result.stderr, (
            f"make -n {target} {extra}: target missing — "
            f"CR-00059 must land all four recipes\n{result.stderr}"
        )
        assert result.returncode == 0, (
            f"make -n {target} {extra}: parse failed (rc={result.returncode})\n{result.stderr}"
        )
