"""I-00085: regression test for .mypy_cache/ false-positive gitleaks findings.

Synthetic .mypy_cache/ payload (mirroring the CR-00053 finding) is run through
gitleaks with the project's actual .gitleaks.toml config.  After the fix, the
cache directory is in the allowlist and gitleaks exits 0.  A control test
verifies that real secrets at non-allowlisted paths are still detected.
"""

import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # tests/integration/ → repo root
GITLEAKS_CONFIG = PROJECT_ROOT / ".gitleaks.toml"


def _gitleaks_available() -> bool:
    try:
        subprocess.run(["gitleaks", "version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _run_gitleaks(source: Path) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        [
            "gitleaks",
            "detect",
            "--no-git",
            "--source",
            str(source),
            "--config",
            str(GITLEAKS_CONFIG),
            "--report-format",
            "json",
            "--report-path",
            str(source / "_report.json"),
        ],
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(not _gitleaks_available(), reason="gitleaks binary not found on PATH")
def test_i00085_mypy_cache_does_not_trigger_false_positives(tmp_path: Path) -> None:
    """Synthetic .mypy_cache/ payload mirroring the CR-00053 finding
    (`threading.local` matches the iw-internal-fqdn rule) must NOT be
    flagged.  FAILS pre-fix, PASSES post-fix.
    """
    cache = tmp_path / ".mypy_cache" / "3.12"
    cache.mkdir(parents=True)
    # Same string CR-00053's S16 flagged on .mypy_cache/3.12/threading.data.json
    (cache / "threading.data.json").write_text('{"fullname": "threading.local"}')

    result = _run_gitleaks(tmp_path)

    assert result.returncode == 0, (
        f"gitleaks must allowlist .mypy_cache/; stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest.mark.skipif(not _gitleaks_available(), reason="gitleaks binary not found on PATH")
def test_i00085_real_secret_still_detected(tmp_path: Path) -> None:
    """Control test: the allowlist additions must NOT mask real secrets.
    Place an AWS-shaped key (distinct from the AKIAIOSFODNN7EXAMPLE
    pattern that is allowlisted in .gitleaks.toml regexes) at a
    non-allowlisted path; gitleaks must detect it.  Passes pre- and
    post-fix — guards against over-broad allowlist edits.
    """
    target = tmp_path / "leak_target"
    target.mkdir()
    # AWS access key shape (AKIA + 16 alphanumerics) that does NOT match the
    # documented-example regex AKIAIOSFODNN7EXAMPLE; suffix chosen to avoid the
    # gitleaks docs-example allowlist entirely.
    (target / "config.py").write_text('AWS_ACCESS_KEY = "AKIA1234567890ABCDEF"\n')

    result = _run_gitleaks(tmp_path)

    assert result.returncode != 0, (
        "gitleaks must flag AKIA1234567890ABCDEF at leak_target/config.py"
    )
    # gitleaks emits the findings summary to stderr; the JSON report goes to stdout
    combined = result.stdout + result.stderr
    assert "AKIA1234567890ABCDEF" in combined or "leaks found" in combined
