"""Unit tests for `scripts/check_test_assertions.py` — the AST assertion scanner.

CR-00046 (P1-CR-A) — RED-first tests. The scanner does not exist when these
tests are first written; they fail with `ModuleNotFoundError` / `ImportError`
until the scanner script lands.

The four detected categories:
  no-assert    — function body has no assertion of any kind
  tautology    — every assertion in the body matches a tautological form
  mock-only    — every assertion is a `mock.assert_called*` / `assert_await*`
  broad-raises — `pytest.raises(Exception)` (or BaseException) without `match=`

Every test in this file uses real, specific assertions — the scanner runs
against this very file at S05 (dogfooding). Vacuous tests here would be a
spectacular own goal.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Path to the scanner under test. This import is intentionally lazy/indirect
# (we shell out to it) so the test file collects cleanly during the RED phase
# — the failure surfaces as a CalledProcessError / FileNotFoundError on the
# first test that runs the script, not at collection time.
SCANNER = Path(__file__).resolve().parents[2] / "scripts" / "check_test_assertions.py"


def run_scanner(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the scanner with given args; return CompletedProcess (no check)."""
    return subprocess.run(
        [sys.executable, str(SCANNER), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Module-level smoke — the scanner must be importable as a python script
# ---------------------------------------------------------------------------


def test_scanner_script_exists() -> None:
    """Scanner file must exist at scripts/check_test_assertions.py."""
    assert SCANNER.is_file(), f"scanner missing at {SCANNER}"


def test_scanner_help_runs() -> None:
    """Scanner must accept --help and exit 0."""
    result = run_scanner("--help")
    assert result.returncode == 0
    assert "baseline" in result.stdout.lower() or "baseline" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Category: no-assert
# ---------------------------------------------------------------------------


def test_no_assert_positive_is_flagged(tmp_path: Path) -> None:
    """`def test_x(): result = foo()` — no assertion of any kind → flagged."""
    _write(
        tmp_path,
        "test_a.py",
        "def test_no_assert():\n    result = foo()\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    cats = [v["category"] for v in payload["violations"]]
    assert "no-assert" in cats
    assert result.returncode == 1


def test_no_assert_negative_with_assert_is_not_flagged(tmp_path: Path) -> None:
    """`def test_x(): result = foo(); assert result == 42` — not flagged."""
    _write(
        tmp_path,
        "test_a.py",
        "def test_with_specific_assert():\n    result = foo()\n    assert result == 42\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    assert payload["violations"] == []
    assert result.returncode == 0


def test_no_assert_negative_pytest_raises_counts(tmp_path: Path) -> None:
    """A `pytest.raises(ValueError)` block counts as an assertion."""
    _write(
        tmp_path,
        "test_a.py",
        "import pytest\n"
        "def test_with_raises():\n"
        "    with pytest.raises(ValueError):\n"
        "        foo()\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    cats = [v["category"] for v in payload["violations"]]
    assert "no-assert" not in cats


# ---------------------------------------------------------------------------
# Category: tautology — sub-cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        # assert True
        "def test_t(): assert True\n",
        # assert <bare Name>
        "def test_t():\n    x = foo()\n    assert x\n",
        # assert x == x (same Name both sides)
        "def test_t():\n    x = foo()\n    assert x == x\n",
        # assert isinstance(x, T) — the whole assertion is isinstance
        "def test_t():\n    x = foo()\n    assert isinstance(x, dict)\n",
        # assert x is not None
        "def test_t():\n    x = foo()\n    assert x is not None\n",
        # assert len(x) > 0
        "def test_t():\n    x = foo()\n    assert len(x) > 0\n",
        # assert len(x) >= 1
        "def test_t():\n    x = foo()\n    assert len(x) >= 1\n",
        # assert len(x) != 0
        "def test_t():\n    x = foo()\n    assert len(x) != 0\n",
        # assert "k" in x
        'def test_t():\n    x = foo()\n    assert "k" in x\n',
    ],
)
def test_tautology_positive_each_subcase(tmp_path: Path, body: str) -> None:
    _write(tmp_path, "test_a.py", body)
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    cats = [v["category"] for v in payload["violations"]]
    assert "tautology" in cats, (
        f"body did not produce tautology: {body!r}; violations={payload['violations']}"
    )
    assert result.returncode == 1


def test_tautology_negative_mixed_with_specific_assert_is_not_flagged(
    tmp_path: Path,
) -> None:
    """A test with one tautological assert + one specific assert is OK."""
    _write(
        tmp_path,
        "test_a.py",
        "def test_mixed():\n"
        "    r = foo()\n"
        "    assert isinstance(r, dict)\n"
        '    assert r["k"] == 42\n',
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    cats = [v["category"] for v in payload["violations"]]
    assert "tautology" not in cats


def test_tautology_negative_len_equality_is_specific(tmp_path: Path) -> None:
    """`assert len(r) == 3` is a specific equality, not tautological."""
    _write(
        tmp_path,
        "test_a.py",
        "def test_specific_len():\n    r = foo()\n    assert len(r) == 3\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    cats = [v["category"] for v in payload["violations"]]
    assert "tautology" not in cats


# ---------------------------------------------------------------------------
# Category: mock-only
# ---------------------------------------------------------------------------


def test_mock_only_positive_is_flagged(tmp_path: Path) -> None:
    """Only assertion is mock.assert_called_once → flagged mock-only."""
    _write(
        tmp_path,
        "test_a.py",
        "def test_mock_only():\n    foo()\n    mock_dep.assert_called_once()\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    cats = [v["category"] for v in payload["violations"]]
    assert "mock-only" in cats
    assert result.returncode == 1


def test_mock_only_negative_with_specific_assert_is_not_flagged(
    tmp_path: Path,
) -> None:
    """A real assert plus mock.assert_called_once → not flagged."""
    _write(
        tmp_path,
        "test_a.py",
        "def test_mock_plus_real():\n"
        "    result = foo()\n"
        "    assert result == 42\n"
        "    mock_dep.assert_called_once()\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    cats = [v["category"] for v in payload["violations"]]
    assert "mock-only" not in cats


def test_mock_only_negative_assert_called_on_non_mock_name(tmp_path: Path) -> None:
    """`session.assert_called_once()` — receiver isn't a mock identifier."""
    _write(
        tmp_path,
        "test_a.py",
        "def test_non_mock_receiver():\n    foo()\n    session.assert_called_once()\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    cats = [v["category"] for v in payload["violations"]]
    assert "mock-only" not in cats


# ---------------------------------------------------------------------------
# Category: broad-raises
# ---------------------------------------------------------------------------


def test_broad_raises_exception_no_match_is_flagged(tmp_path: Path) -> None:
    """`with pytest.raises(Exception): ...` no match= → flagged broad-raises."""
    _write(
        tmp_path,
        "test_a.py",
        "import pytest\ndef test_broad():\n    with pytest.raises(Exception):\n        foo()\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    cats = [v["category"] for v in payload["violations"]]
    assert "broad-raises" in cats
    assert result.returncode == 1


def test_broad_raises_with_match_is_not_flagged(tmp_path: Path) -> None:
    """`pytest.raises(Exception, match="...")` → not flagged."""
    _write(
        tmp_path,
        "test_a.py",
        "import pytest\n"
        "def test_match():\n"
        '    with pytest.raises(Exception, match="not found"):\n'
        "        foo()\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    cats = [v["category"] for v in payload["violations"]]
    assert "broad-raises" not in cats


def test_broad_raises_specific_exception_is_not_flagged(tmp_path: Path) -> None:
    """`pytest.raises(ValueError)` → not flagged (specific type)."""
    _write(
        tmp_path,
        "test_a.py",
        "import pytest\n"
        "def test_value_error():\n"
        "    with pytest.raises(ValueError):\n"
        "        foo()\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    cats = [v["category"] for v in payload["violations"]]
    assert "broad-raises" not in cats


# ---------------------------------------------------------------------------
# Baseline mechanic
# ---------------------------------------------------------------------------


def test_baseline_allows_known_offender_flags_new(tmp_path: Path) -> None:
    """`--baseline <path>` admits listed offenders; a new one is flagged."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    _write(
        tests_dir,
        "test_old.py",
        "def test_old_offender():\n    foo()\n",
    )

    # Generate baseline from current state.
    baseline_path = tmp_path / "baseline.txt"
    result_write = run_scanner("--write-baseline", str(baseline_path), str(tests_dir))
    assert result_write.returncode == 0, result_write.stderr

    # No new violations → exit 0.
    result_ok = run_scanner("--baseline", str(baseline_path), str(tests_dir))
    assert result_ok.returncode == 0, result_ok.stdout + result_ok.stderr

    # Introduce a NEW offender → exit 1, reports only the new one.
    _write(
        tests_dir,
        "test_new.py",
        "def test_new_offender():\n    foo()\n",
    )
    result_fail = run_scanner("--baseline", str(baseline_path), "--json", str(tests_dir))
    assert result_fail.returncode == 1
    payload = json.loads(result_fail.stdout)
    paths = [v["path"] for v in payload["violations"]]
    assert any("test_new.py" in p for p in paths)
    assert not any("test_old.py" in p for p in paths)


def test_write_baseline_overwrites_with_sorted_entries(tmp_path: Path) -> None:
    """`--write-baseline <path>` regenerates the file with sorted entries."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    _write(
        tests_dir,
        "test_b.py",
        "def test_zeta(): foo()\n",
    )
    _write(
        tests_dir,
        "test_a.py",
        "def test_alpha(): foo()\n",
    )
    baseline_path = tmp_path / "baseline.txt"
    # Pre-populate with garbage to confirm overwrite, not append.
    baseline_path.write_text("STALE_GARBAGE\n", encoding="utf-8")

    result = run_scanner("--write-baseline", str(baseline_path), str(tests_dir))
    assert result.returncode == 0, result.stderr

    text = baseline_path.read_text(encoding="utf-8")
    assert "STALE_GARBAGE" not in text
    # Each entry is `path::test_name # category`.
    data_lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    assert len(data_lines) == 2
    assert data_lines == sorted(data_lines)
    # Both tests appear with their no-assert category.
    assert any("test_alpha" in line and "no-assert" in line for line in data_lines)
    assert any("test_zeta" in line and "no-assert" in line for line in data_lines)
    # Comment header is present.
    assert any(line.startswith("#") for line in text.splitlines())


def test_strict_ignores_baseline(tmp_path: Path) -> None:
    """`--strict` reports every violation regardless of baseline."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    _write(tests_dir, "test_a.py", "def test_x(): foo()\n")
    baseline_path = tmp_path / "baseline.txt"
    run_scanner("--write-baseline", str(baseline_path), str(tests_dir))

    result = run_scanner("--strict", "--baseline", str(baseline_path), "--json", str(tests_dir))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert len(payload["violations"]) == 1
    assert payload["violations"][0]["category"] == "no-assert"


# ---------------------------------------------------------------------------
# Output shapes
# ---------------------------------------------------------------------------


def test_json_output_shape(tmp_path: Path) -> None:
    """`--json` emits {"violations": [{path,line,category,test_name,message}, ...]}."""
    _write(
        tmp_path,
        "test_a.py",
        "def test_no_assert():\n    foo()\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    assert "violations" in payload
    assert isinstance(payload["violations"], list)
    assert len(payload["violations"]) == 1
    v = payload["violations"][0]
    assert set(v.keys()) >= {"path", "line", "category", "test_name", "message"}
    assert v["category"] == "no-assert"
    assert v["test_name"] == "test_no_assert"
    assert v["line"] == 1
    assert isinstance(v["message"], str)
    assert v["message"]


def test_human_readable_output_format(tmp_path: Path) -> None:
    """Default output is `path:line: <category>: <test_name>: <message>` per violation."""
    _write(
        tmp_path,
        "test_a.py",
        "def test_no_assert():\n    foo()\n",
    )
    result = run_scanner("--strict", str(tmp_path))
    assert result.returncode == 1
    # Find at least one line matching the expected shape.
    lines = result.stdout.splitlines()
    match = [ln for ln in lines if "no-assert" in ln and "test_no_assert" in ln and ":" in ln]
    assert match, f"no matching line in stdout: {result.stdout!r}"


# ---------------------------------------------------------------------------
# noqa opt-out
# ---------------------------------------------------------------------------


def test_noqa_assertion_scanner_suppresses(tmp_path: Path) -> None:
    """`# noqa: assertion-scanner` on the def line suppresses the report."""
    _write(
        tmp_path,
        "test_a.py",
        "def test_no_assert():  # noqa: assertion-scanner\n    foo()\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    assert payload["violations"] == []
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# conftest exclusion
# ---------------------------------------------------------------------------


def test_conftest_is_skipped(tmp_path: Path) -> None:
    """`tests/conftest.py` and any `conftest.py` are not scanned."""
    nested = tmp_path / "sub"
    nested.mkdir()
    # A test-shaped function inside conftest.py — would be flagged if scanned.
    _write(
        nested,
        "conftest.py",
        "def test_in_conftest():\n    foo()\n",
    )
    result = run_scanner("--strict", "--json", str(tmp_path))
    payload = json.loads(result.stdout)
    assert payload["violations"] == []
