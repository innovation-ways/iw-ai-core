"""Fix recipes for release process compliance checks (OSS-REL-*)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import register
from .base import FixPreview

if TYPE_CHECKING:
    from pathlib import Path


class ChangelogRecipe:
    """Fix recipe that creates a CHANGELOG.md when one is missing.

    Addresses OSS-REL-01: absence of a structured changelog. Generates a
    Keep-a-Changelog formatted stub with an Unreleased section.
    """

    check_id = "OSS-REL-01"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        from textwrap import dedent

        candidates = ["CHANGELOG.md", "CHANGELOG", "HISTORY.md", "NEWS.md"]
        for c in candidates:
            if (repo_root / c).exists():
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="CHANGELOG already exists.",
                )
        target = repo_root / "CHANGELOG.md"
        content = dedent("""\
            # Changelog

            All notable changes to this project will be documented in this file.

            The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
            and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

            ## [Unreleased]

            ### Added
            - (desc)

            ### Changed
            - (desc)

            ### Fixed
            - (desc)
            """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated CHANGELOG.md template.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(ChangelogRecipe())


class ReleasePleaseRecipe:
    """Fix recipe that creates or upgrades a release-please GitHub Actions workflow.

    Addresses OSS-REL-03: absence of an automated release process, or use of
    the deprecated release-please-action@v3. Upgrades existing v3 references
    to v4 in-place; creates a new workflow file when none exists.
    """

    check_id = "OSS-REL-03"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        from textwrap import dedent

        target = repo_root / ".github" / "workflows" / "release-please.yml"
        if target.exists():
            text = target.read_text()
            if "googleapis/release-please-action@v4" in text:
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="release-please.yml already uses v4.",
                )
            new_text = text.replace("release-please-action@v3", "release-please-action@v4").replace(
                "googleapis/release-please-action@v3",
                "googleapis/release-please-action@v4",
            )
            import difflib

            diff = "".join(
                difflib.unified_diff(text.splitlines(), new_text.splitlines(), lineterm="")
            )
            return FixPreview(
                target_files=[target],
                full_contents={},
                diffs={target: diff},
                notes="Updating release-please-action to v4.",
            )
        content = dedent("""\
            name: Release Please

            on:
              push:
                branches:
                  - main

            permissions:
              contents: write

            jobs:
              release-please:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
                  - uses: googleapis/release-please-action@v4
                    with:
                      token: ${{ secrets.GITHUB_TOKEN }}
                      release-type: node
            """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated release-please.yml v4 workflow.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(ReleasePleaseRecipe())


class AttestBuildProvenanceRecipe:
    """Fix recipe that checks for build provenance attestation in CI workflows.

    Addresses OSS-REL-04: absence of actions/attest-build-provenance in any
    workflow. This check is informational only — the recipe reports the finding
    but does not write files, because provenance attestation requires manual
    workflow authoring specific to the project's build process.
    """

    check_id = "OSS-REL-04"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        wf_dir = repo_root / ".github" / "workflows"
        if not wf_dir.exists():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="No workflows directory.",
            )
        for wf in wf_dir.glob("*.yml"):
            if "actions/attest-build-provenance" in wf.read_text():
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="attest-build-provenance already referenced.",
                )
        return FixPreview(
            target_files=[],
            full_contents={},
            diffs={},
            notes=(
                "attest-build-provenance not found in any workflow — "
                "requires manual workflow authoring."
            ),
        )

    def apply(self, repo_root: Path) -> FixPreview:
        return self.preview(repo_root)


register(AttestBuildProvenanceRecipe())
