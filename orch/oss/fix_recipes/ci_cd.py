"""Fix recipes for CI/CD workflow compliance checks (OSS-CI-*)."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, Any

from . import register
from .base import FixPreview

if TYPE_CHECKING:
    from pathlib import Path


def _render_jinja2(template_path: Path, context: dict[str, Any]) -> str:
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        loader = FileSystemLoader(str(template_path.parent))
        env = Environment(loader=loader, autoescape=select_autoescape())
        template = env.get_template(template_path.name)
        return template.render(**context)
    except Exception:
        return ""


def _load_config(repo_root: Path) -> dict[str, Any]:
    config_path = repo_root / ".iw" / "oss-publish.toml"
    if not config_path.exists():
        return {}
    import tomllib

    try:
        return tomllib.loads(config_path.read_text())
    except Exception:
        return {}


class CodeqlWorkflowRecipe:
    """Fix recipe that generates a GitHub Actions CodeQL analysis workflow.

    Addresses OSS-CI-06: absence of a static analysis / SAST workflow.
    """

    check_id = "OSS-CI-06"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        target = repo_root / ".github" / "workflows" / "codeql.yml"
        if target.exists():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="codeql.yml already exists.",
            )
        _load_config(repo_root)
        content = dedent("""\
            name: CodeQL

            on:
              push:
                branches: [main]
              pull_request:
                branches: [main]

            jobs:
              codeql:
                runs-on: ubuntu-latest
                permissions:
                  security-events: write
                  contents: read

              steps:
                - uses: actions/checkout@v4

                - name: Initialize CodeQL
                  uses: github/codeql-action/init@v3
                  with:
                    languages: python

                - name: Perform Analysis
                  uses: github/codeql-action/analyze@v3
                  with:
                    category: "/language:python"
            """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated CodeQL workflow.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(CodeqlWorkflowRecipe())


class ScorecardWorkflowRecipe:
    """Fix recipe that generates an OpenSSF Scorecard GitHub Actions workflow.

    Addresses OSS-CI-07: absence of a supply-chain security scorecard workflow.
    """

    check_id = "OSS-CI-07"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        target = repo_root / ".github" / "workflows" / "scorecard.yml"
        if target.exists():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="scorecard.yml already exists.",
            )
        _load_config(repo_root)
        content = dedent("""\
            name: OpenSSF Scorecard

            on:
              workflow_dispatch:
              schedule:
                - cron: "0 0 * * 0"

            permissions:
              contents: read

            jobs:
              scorecard:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
                    with:
                      persist-credentials: false

                  - name: Run Scorecard
                    uses: ossf/scorecard-action@v2
                    with:
                      results-file: results.sarif
                      results-file-flag: scorecard-results
                      publish-results: true

                  - name: Upload to CodeSec
                    uses: github/codeql-action/upload-sarif@v3
                    with:
                      sarif_file: results.sarif
            """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated OpenSSF Scorecard workflow.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(ScorecardWorkflowRecipe())


class DependabotRecipe:
    """Fix recipe that generates a Dependabot configuration file.

    Addresses OSS-CI-08: absence of automated dependency update configuration.
    """

    check_id = "OSS-CI-08"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        target = repo_root / ".github" / "dependabot.yml"
        if target.exists():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="dependabot.yml already exists.",
            )
        content = dedent("""\
            version: 2
            updates:
              - package-ecosystem: "pip"
                directory: "/"
                schedule:
                  interval: "weekly"
                open-pull-requests-limit: 10

              - package-ecosystem: "github-actions"
                directory: "/"
                schedule:
                  interval: "weekly"
            """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated Dependabot configuration.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(DependabotRecipe())


class ComplianceScanWorkflowRecipe:
    """Fix recipe that generates an OSS compliance scan GitHub Actions workflow.

    Addresses OSS-CI-09: absence of an automated compliance gate in CI.
    """

    check_id = "OSS-CI-09"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        target = repo_root / ".github" / "workflows" / "compliance-scan.yml"
        if target.exists():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="compliance-scan.yml already exists.",
            )
        content = dedent("""\
            name: OSS Compliance Scan

            on:
              push:
                branches: [main]
              pull_request:
                branches: [main]

            jobs:
              oss-scan:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4

                  - name: Install tools
                    run: |
                      bash .claude/skills/iw-oss-publish/scripts/install_tools.sh

                  - name: Run OSS scan
                    run: |
                      uv run iw oss scan --project .
                  """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated compliance scan workflow.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(ComplianceScanWorkflowRecipe())


class ActionPinningRecipe:
    """Fix recipe that pins GitHub Actions to their commit SHAs using pinact.

    Addresses OSS-CI-02: workflow actions referenced by mutable tag rather than
    an immutable commit SHA, which is a supply-chain security risk.
    """

    check_id = "OSS-CI-02"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        import subprocess

        wf_dir = repo_root / ".github" / "workflows"
        if not wf_dir.exists():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="No workflows directory.",
            )
        try:
            r = subprocess.run(
                ["pinact", "run", "--check"],  # noqa: S607
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode == 0:
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="All actions already pinned.",
                )
        except Exception:  # noqa: S110
            pass
        try:
            result = subprocess.run(
                ["pinact", "run"],  # noqa: S607
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=60,
            )
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes=f"pinact ran (exit={result.returncode}); see live output for changes.",
            )
        except Exception as exc:
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes=f"pinact not available: {exc}",
            )

    def apply(self, repo_root: Path) -> FixPreview:
        return self.preview(repo_root)


register(ActionPinningRecipe())
