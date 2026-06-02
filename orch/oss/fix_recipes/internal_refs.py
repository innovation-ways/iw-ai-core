"""Fix recipe for SBOM generation compliance checks (OSS-DEP-*)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import register
from .base import FixPreview

if TYPE_CHECKING:
    from pathlib import Path


class SbomRecipe:
    """Fix recipe that guides SBOM generation using syft.

    Addresses OSS-DEP-05: absence of a Software Bill of Materials. The recipe
    does not run syft directly — it checks for the tool and provides the
    operator with the correct manual command, because SBOM generation may take
    several minutes and produce large files.
    """

    check_id = "OSS-DEP-05"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        iw_dir = repo_root / ".iw"
        spdx = iw_dir / "sbom.spdx.json"
        if spdx.exists():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="SBOM already generated (spdx at .iw/sbom.spdx.json).",
            )
        if not self._has_tool("syft"):
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes=(
                    "syft not available — run "
                    "`bash .claude/skills/iw-oss-publish/scripts/install_tools.sh` first."
                ),
            )
        return FixPreview(
            target_files=[],
            full_contents={},
            diffs={},
            notes=(
                "SBOM generation requires syft — run "
                "`syft scan dir:<path> -o spdx-json=.iw/sbom.spdx.json` manually."
            ),
        )

    def apply(self, repo_root: Path) -> FixPreview:
        return self.preview(repo_root)

    def _has_tool(self, name: str) -> bool:
        import shutil

        return shutil.which(name) is not None


register(SbomRecipe())
