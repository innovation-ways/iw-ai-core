"""Driver.js MIT license lockdown tests (AC7).

These tests enforce Acceptance Criterion AC7 ("Apache 2.0 OSS license
compatibility") so a future agent cannot accidentally ship without the MIT
attribution. Pure file-content assertions — no TestClient needed.

Skip with a clear pytest.skip() if vendored Driver.js is not present yet;
in CI on the merged work item all files MUST exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Project root — resolved relative to this file's location
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DRIVER_VENDOR_DIR = PROJECT_ROOT / "dashboard" / "static" / "vendor" / "driver"
LICENSE_FILE = DRIVER_VENDOR_DIR / "LICENSE"
IIFE_FILE = DRIVER_VENDOR_DIR / "driver.js.iife.js"
THIRD_PARTY_LICENSES = PROJECT_ROOT / "THIRD_PARTY_LICENSES.md"
VENDOR_DIR = PROJECT_ROOT / "dashboard" / "static" / "vendor"

# Known AGPL-licensed onboarding library names that must NOT be vendored.
AGPL_FORBIDDEN_SUBDIRS = {"shepherd", "intro", "intro-js", "tourguide", "shepherd.js"}


def _agpl_license_paths() -> list[Path]:
    """Walk vendor/ and return paths to LICENSE files containing 'AGPL'."""
    agpl_paths: list[Path] = []
    if not VENDOR_DIR.is_dir():
        return agpl_paths
    for license_path in VENDOR_DIR.glob("**/LICENSE"):
        try:
            content = license_path.read_text(encoding="utf-8", errors="ignore")
            if "AGPL" in content or "GNU AFFERO GENERAL PUBLIC LICENSE" in content:
                agpl_paths.append(license_path)
        except Exception:
            pass
    return agpl_paths


class TestDriverJsLicense:
    """AC7: Driver.js MIT licensing invariants."""

    def test_driver_license_file_exists_and_is_mit(self) -> None:
        """LICENSE file exists, is non-empty, and contains canonical MIT text."""
        if not LICENSE_FILE.exists():
            pytest.skip("Vendored Driver.js LICENSE not present yet")
        content = LICENSE_FILE.read_text(encoding="utf-8")
        assert content.strip(), "LICENSE file should not be empty"
        assert "MIT" in content, "LICENSE should declare MIT license"
        assert "Permission is hereby granted, free of charge" in content, (
            "LICENSE should contain the canonical MIT opening grant clause"
        )

    def test_driver_iife_has_mit_header(self) -> None:
        """The first ~40 lines of driver.js.iife.js include the MIT header comment."""
        if not IIFE_FILE.exists():
            pytest.skip("Vendored Driver.js IIFE not present yet")
        # Read only the first 40 lines to avoid pulling the whole minified file.
        lines = IIFE_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()[:40]
        header_text = "\n".join(lines)
        assert "MIT" in header_text, (
            "MIT license header comment not found in the first 40 lines of "
            "driver.js.iife.js — upstream header may have been stripped"
        )

    def test_third_party_licenses_lists_driver(self) -> None:
        """THIRD_PARTY_LICENSES contains an MIT entry for Driver.js."""
        if not THIRD_PARTY_LICENSES.exists():
            pytest.skip("THIRD_PARTY_LICENSES not present yet")
        content = THIRD_PARTY_LICENSES.read_text(encoding="utf-8")
        assert "Driver.js" in content, "THIRD_PARTY_LICENSES should list Driver.js"
        assert "MIT" in content, "THIRD_PARTY_LICENSES Driver.js entry should declare MIT license"

    def test_no_agpl_onboarding_lib_vendored(self) -> None:
        """No forbidden AGPL onboarding library is present under dashboard/static/vendor/."""
        # Check for forbidden directory names.
        forbidden_found: list[str] = []
        if VENDOR_DIR.is_dir():
            for subdir in VENDOR_DIR.iterdir():
                if subdir.is_dir() and subdir.name.lower() in AGPL_FORBIDDEN_SUBDIRS:
                    forbidden_found.append(str(subdir.relative_to(PROJECT_ROOT)))

        # Check for any LICENSE file containing AGPL text.
        agpl_paths = _agpl_license_paths()

        assert not forbidden_found, (
            "Forbidden AGPL onboarding library directories found: " + ", ".join(forbidden_found)
        )
        assert not agpl_paths, (
            "LICENSE files containing AGPL text found under vendor/: "
            + ", ".join(str(p.relative_to(PROJECT_ROOT)) for p in agpl_paths)
        )
