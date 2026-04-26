from __future__ import annotations

from typing import TYPE_CHECKING

from . import register
from .base import FixPreview

if TYPE_CHECKING:
    from pathlib import Path


class SbomRecipe:
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
