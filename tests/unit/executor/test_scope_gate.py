"""Unit tests for executor/scope_gate.py — bundled P1 coverage for AC7.

Tests executor/scope_gate.py via subprocess invocation.
Each test uses its own tmp_path manifest to stay isolated.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def scope_gate(
    manifest: dict[str, Any],
    item_id: str,
    stdin_paths: list[str],
    tmp_path: Path,
) -> subprocess.CompletedProcess[str]:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return subprocess.run(
        [sys.executable, "executor/scope_gate.py", str(manifest_path), item_id],
        input="\n".join(stdin_paths),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Legacy mode
# ---------------------------------------------------------------------------


class TestLegacyMode:
    def test_legacy_mode_no_scope_field_exits_zero(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999"}
        result = scope_gate(manifest, "F-99999", ["dashboard/routers/other.py"], tmp_path)
        assert result.returncode == 0
        assert "skipping gate" in result.stderr

    def test_legacy_mode_empty_allowed_paths_exits_zero(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999", "scope": {"allowed_paths": []}}
        result = scope_gate(manifest, "F-99999", ["dashboard/routers/other.py"], tmp_path)
        assert result.returncode == 0
        assert "skipping gate" in result.stderr


# ---------------------------------------------------------------------------
# Exact path match
# ---------------------------------------------------------------------------


class TestExactPath:
    def test_exact_path_match_allows(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999", "scope": {"allowed_paths": ["dashboard/routers/items.py"]}}
        result = scope_gate(manifest, "F-99999", ["dashboard/routers/items.py"], tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_exact_path_mismatch_flags_as_violation(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999", "scope": {"allowed_paths": ["dashboard/routers/items.py"]}}
        result = scope_gate(manifest, "F-99999", ["dashboard/routers/other.py"], tmp_path)
        assert result.returncode == 1
        assert "dashboard/routers/other.py" in result.stdout


# ---------------------------------------------------------------------------
# dir/** prefix glob
# ---------------------------------------------------------------------------


class TestDirStarStar:
    def test_dir_double_star_allows_nested(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999", "scope": {"allowed_paths": ["dashboard/routers/**"]}}
        result = scope_gate(
            manifest,
            "F-99999",
            ["dashboard/routers/items.py", "dashboard/routers/sub/nested.py"],
            tmp_path,
        )
        assert result.returncode == 0

    def test_dir_double_star_blocks_siblings(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999", "scope": {"allowed_paths": ["dashboard/routers/**"]}}
        result = scope_gate(manifest, "F-99999", ["dashboard/app.py"], tmp_path)
        assert result.returncode == 1
        assert "dashboard/app.py" in result.stdout


# ---------------------------------------------------------------------------
# fnmatch single-level wildcard
# ---------------------------------------------------------------------------


class TestFnmatchWildcard:
    def test_fnmatch_single_level_wildcard(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999", "scope": {"allowed_paths": ["dir/*.py"]}}
        result = scope_gate(manifest, "F-99999", ["dir/foo.py"], tmp_path)
        assert result.returncode == 0

    def test_fnmatch_blocks_nested(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999", "scope": {"allowed_paths": ["dir/*.py"]}}
        result = scope_gate(manifest, "F-99999", ["dir/sub/foo.py"], tmp_path)
        assert result.returncode == 0

    def test_fnmatch_blocks_non_py(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999", "scope": {"allowed_paths": ["dir/*.py"]}}
        result = scope_gate(manifest, "F-99999", ["dir/foo.js"], tmp_path)
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# Implicit ai-dev/active and ai-dev/archive allow
# ---------------------------------------------------------------------------


class TestImplicitAllows:
    def test_implicit_ai_dev_active_allow(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999", "scope": {"allowed_paths": ["x.py"]}}
        result = scope_gate(
            manifest,
            "F-99999",
            ["ai-dev/active/F-99999/some_report.md", "x.py"],
            tmp_path,
        )
        assert result.returncode == 0

    def test_implicit_ai_dev_archive_allow(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999", "scope": {"allowed_paths": ["x.py"]}}
        result = scope_gate(
            manifest,
            "F-99999",
            ["ai-dev/archive/F-99999/evidence.png", "x.py"],
            tmp_path,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Violation listing
# ---------------------------------------------------------------------------


class TestViolationListing:
    def test_violation_listing_preserves_input_order(self, tmp_path: Path) -> None:
        manifest = {"id": "F-99999", "scope": {"allowed_paths": ["x.py"]}}
        result = scope_gate(manifest, "F-99999", ["z.py", "a.py", "m.py"], tmp_path)
        assert result.returncode == 1
        lines = result.stdout.strip().splitlines()
        assert lines == ["z.py", "a.py", "m.py"]


# ---------------------------------------------------------------------------
# Malformed / missing manifest
# ---------------------------------------------------------------------------


class TestMalformedManifest:
    def test_malformed_manifest_exits_two(self, tmp_path: Path) -> None:
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("{not valid json")
        result = subprocess.run(
            [sys.executable, "executor/scope_gate.py", str(bad_path), "F-99999"],
            input="x.py\n",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "error" in result.stderr.lower() or "json" in result.stderr.lower()

    def test_missing_manifest_exits_two(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, "executor/scope_gate.py", "/no/such/path.json", "F-99999"],
            input="x.py\n",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
