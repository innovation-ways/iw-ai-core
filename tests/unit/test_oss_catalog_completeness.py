"""CR-00022 AC4: every check_id has a catalog entry with non-empty mandatory fields."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

CATALOG_PATH = Path(__file__).parents[2] / "dashboard" / "services" / "oss_check_catalog.yaml"


def _ast_check_ids() -> set[str]:
    """Extract all Finding() check_ids from the checks scripts."""
    checks_dir = Path(__file__).parents[2] / "skills" / "iw-oss-publish" / "scripts" / "checks"
    ids: set[str] = set()

    if not checks_dir.exists():
        pytest.skip(f"Checks directory not found: {checks_dir}")

    for path in checks_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Finding":
                for kw in node.keywords:
                    if kw.arg == "id" and isinstance(kw.value, ast.Constant):
                        ids.add(kw.value.value)
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
