"""CR-00022 AC4: every check_id has a catalog entry with non-empty mandatory fields.

Many checks construct their finding's check_id dynamically — passed as a
positional arg to a helper (`_result_to_finding`, `_probe`, `_gitleaks_scan`)
or pulled from a dict driving a loop (`ci_cd.wf_files`). Inspecting only
`Finding(id=...)` keyword args misses those, which is how OSS-REF-01..05,
OSS-CI-06..09, OSS-SEC-01..02 and OSS-TM-02..05 silently shipped without
catalog copy and produced empty modal bodies on the dashboard. The
enumeration here walks every string literal in the check modules and keeps
those matching the canonical ``OSS-XX-NN`` shape — robust against the
constructor pattern variation.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

CATALOG_PATH = Path(__file__).parents[2] / "dashboard" / "services" / "oss_check_catalog.yaml"
CHECKS_DIR = Path(__file__).parents[2] / "skills" / "iw-oss-publish" / "scripts" / "checks"

# Canonical check_id shape: "OSS-" + alphabetic prefix + "-" + alphanumeric suffix.
# Suffix is alphanumeric so "OSS-REF-ALL" and "OSS-GH-01" both match.
_CHECK_ID_RE = re.compile(r"^OSS-[A-Z]+-[A-Z0-9]+$")


def _ast_check_ids() -> set[str]:
    """Extract every ``OSS-XX-NN`` string literal from the check modules.

    Walks each module's AST and keeps only ``ast.Constant`` string nodes that
    match the canonical check_id shape. AST traversal (rather than a raw text
    grep) ensures matches in comments are ignored — module docstrings still
    count, which is fine because they normally document real IDs anyway.
    """
    ids: set[str] = set()

    if not CHECKS_DIR.exists():
        pytest.skip(f"Checks directory not found: {CHECKS_DIR}")

    for path in CHECKS_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and _CHECK_ID_RE.match(node.value)
            ):
                ids.add(node.value)
    return ids


class TestCatalogCompleteness:
    def test_every_check_id_has_catalog_entry(self) -> None:
        if not CATALOG_PATH.exists():
            pytest.skip(f"Catalog not found: {CATALOG_PATH}")

        catalog = yaml.safe_load(CATALOG_PATH.read_text()) or {}
        missing = sorted(_ast_check_ids() - catalog.keys())
        assert not missing, f"Catalog missing entries for: {missing}"

    def test_no_orphan_catalog_entries(self) -> None:
        if not CATALOG_PATH.exists():
            pytest.skip(f"Catalog not found: {CATALOG_PATH}")

        catalog = yaml.safe_load(CATALOG_PATH.read_text()) or {}
        orphans = sorted(catalog.keys() - _ast_check_ids())
        assert not orphans, f"Catalog has orphan entries (no matching check): {orphans}"

    def test_catalog_entries_have_required_fields(self) -> None:
        if not CATALOG_PATH.exists():
            pytest.skip(f"Catalog not found: {CATALOG_PATH}")

        catalog = yaml.safe_load(CATALOG_PATH.read_text()) or {}
        required = {"what_it_checks", "how_it_tests", "risk_if_failing", "how_to_fix"}

        for check_id, entry in catalog.items():
            for field in required:
                entry_val = (
                    entry.get(field, "").strip()
                    if isinstance(entry, dict)
                    else getattr(entry, field, "").strip()
                )
                assert entry_val, f"{check_id}: field '{field}' is missing or empty"

    def test_catalog_all_entries_are_strings(self) -> None:
        if not CATALOG_PATH.exists():
            pytest.skip(f"Catalog not found: {CATALOG_PATH}")

        catalog = yaml.safe_load(CATALOG_PATH.read_text()) or {}

        for check_id, entry in catalog.items():
            assert isinstance(entry, dict), f"{check_id}: entry must be a dict"
            for field in ["what_it_checks", "how_it_tests", "risk_if_failing", "how_to_fix"]:
                assert field in entry, f"{check_id}: missing required field '{field}'"
                assert isinstance(entry[field], str), f"{check_id}.{field} must be a string"
