"""Fix recipes for contributor agreement compliance checks (OSS-CA-*)."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from . import register
from .base import FixPreview

if TYPE_CHECKING:
    from pathlib import Path


class DcoConfigRecipe:
    """Fix recipe that creates a .github/dco.yml DCO enforcement configuration.

    Addresses OSS-CA-01: absence of GitHub App DCO sign-off enforcement.
    """

    check_id = "OSS-CA-01"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        target = repo_root / ".github" / "dco.yml"
        if target.exists():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes=".github/dco.yml already exists.",
            )
        content = dedent("""\
            # DCO (Developer Certificate of Origin)
            # https://github.com/apps/dco
            signoff:
              required: true
              autoIC: true
            """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated .github/dco.yml for DCO enforcement.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(DcoConfigRecipe())


class DcoContributingRecipe:
    """Fix recipe that appends a DCO sign-off section to CONTRIBUTING.md.

    Addresses OSS-CA-02: CONTRIBUTING.md exists but does not document the DCO
    sign-off requirement. No-ops when the file is absent or already contains
    DCO language.
    """

    check_id = "OSS-CA-02"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        candidates = ["CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md"]
        target = None
        for c in candidates:
            p = repo_root / c
            if p.exists():
                target = p
                break
        if target is None:
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="CONTRIBUTING.md not found.",
            )
        text = target.read_text()
        if "signed-off-by" in text.lower() or "developer certificate of origin" in text.lower():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="DCO sign-off already documented.",
            )
        new_text = text.rstrip() + dedent("""

            ## Sign-off Requirement

            All commits must include a Signed-Off-By line to certify the
            [Developer Certificate of Origin](https://developercertificate.org/):

            ```
            Signed-off-by: Your Name <your.email@example.com>
            ```

            Use `git commit -s` to sign off automatically.
            """)
        import difflib

        diff = "".join(difflib.unified_diff(text.splitlines(), new_text.splitlines(), lineterm=""))
        return FixPreview(
            target_files=[target],
            full_contents={},
            diffs={target: diff},
            notes="Appends DCO sign-off section to existing CONTRIBUTING.md.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        if not preview.target_files:
            return preview
        target = preview.target_files[0]
        text = target.read_text()
        if "signed-off-by" in text.lower() or "developer certificate of origin" in text.lower():
            return preview
        new_text = text.rstrip() + dedent("""

            ## Sign-off Requirement

            All commits must include a Signed-Off-By line to certify the
            [Developer Certificate of Origin](https://developercertificate.org/):

            ```
            Signed-off-by: Your Name <your.email@example.com>
            ```

            Use `git commit -s` to sign off automatically.
            """)
        target.write_text(new_text)
        return preview


register(DcoContributingRecipe())
