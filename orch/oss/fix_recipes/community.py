"""Fix recipes for community health file compliance checks (OSS-CH-*)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any

from . import register
from .base import FixPreview


def _load_config(repo_root: Path) -> dict[str, Any]:
    config_path = repo_root / ".iw" / "oss-publish.toml"
    if not config_path.exists():
        return {}
    import tomllib

    try:
        return tomllib.loads(config_path.read_text())
    except Exception:
        return {}


def _render_jinja2(template_path: Path, context: dict[str, Any]) -> str:
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        loader = FileSystemLoader(str(template_path.parent))
        env = Environment(loader=loader, autoescape=select_autoescape())
        template = env.get_template(template_path.name)
        return template.render(**context)
    except Exception:
        return ""


class ReadmeRecipe:
    """Fix recipe that creates a README.md when one is missing.

    Addresses OSS-CH-01: absence of a repository README. Uses the
    iw-oss-publish Jinja2 template when available, otherwise generates a
    minimal placeholder.
    """

    check_id = "OSS-CH-01"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        target = repo_root / "README.md"
        config = _load_config(repo_root)
        tmpl_path = (
            Path(__file__).parent.parent.parent.parent
            / "skills"
            / "iw-oss-publish"
            / "templates"
            / "README.md.j2"
        )
        if tmpl_path.exists():
            gh_org = config.get("company_github_org", "innovation-ways")
            context = {
                "project_name": config.get("project_name", repo_root.name),
                "project_description": config.get("project_description", ""),
                "license": config.get("license", "Apache-2.0"),
                "license_badge_slug": config.get("license", "Apache-2.0").replace(" ", "-"),
                "company_brand": config.get("company_brand", "Innovation Ways"),
                "company_github_org": gh_org,
                "company_contact_email": config.get(
                    "company_contact_email", "info@innovation-ways.com"
                ),
                "coc_version": config.get("coc_version", "2.1"),
                "homepage": config.get(
                    "homepage",
                    f"https://github.com/{gh_org}/{repo_root.name}",
                ),
                "project_is_trademark": False,
                "year": "2026",
            }
            content = _render_jinja2(tmpl_path, context)
        else:
            content = dedent(f"""\
                # {repo_root.name}

                One-line description of what this project does. (Replace this placeholder.)

                ## Installation

                ```bash
                pip install {repo_root.name}
                ```

                ## Usage

                ```bash
                {repo_root.name} --help
                ```
            """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated from iw-oss-publish README template; replace placeholders.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(ReadmeRecipe())


class SecurityMdRecipe:
    """Fix recipe that creates a SECURITY.md vulnerability disclosure policy.

    Addresses OSS-CH-02: absence of a documented security reporting process.
    Checks SECURITY.md, .github/SECURITY.md, and docs/SECURITY.md before
    writing to avoid duplicating an existing policy.
    """

    check_id = "OSS-CH-02"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        candidates = ["SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md"]
        for c in candidates:
            p = repo_root / c
            if p.exists():
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="SECURITY.md already exists.",
                )
        target = repo_root / "SECURITY.md"
        config = _load_config(repo_root)
        tmpl_path = (
            Path(__file__).parent.parent.parent.parent
            / "skills"
            / "iw-oss-publish"
            / "templates"
            / "SECURITY.md.j2"
        )
        if tmpl_path.exists():
            context = {
                "project_name": config.get("project_name", repo_root.name),
                "company_contact_email": config.get(
                    "company_contact_email", "security@innovation-ways.com"
                ),
                "company_brand": config.get("company_brand", "Innovation Ways"),
                "year": "2026",
            }
            content = _render_jinja2(tmpl_path, context)
        else:
            sec_email = config.get("company_contact_email", "security@innovation-ways.com")
            content = dedent(f"""\
                # Security Policy

                ## Supported Versions

                | Version | Supported          |
                | ------- | ------------------ |
                | 1.x     | :white_check_mark: |

                ## Reporting a Vulnerability

                Please report security vulnerabilities to {sec_email}.
                Include as much detail as possible so we can respond quickly and effectively.
                We aim to respond within 48 hours.

                Do not file public issues for security vulnerabilities.
                """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated from iw-oss-publish SECURITY.md template.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(SecurityMdRecipe())


class CodeOfConductRecipe:
    """Fix recipe that creates a Contributor Covenant Code of Conduct.

    Addresses OSS-CH-03: absence of a code of conduct document. Skips
    creation when CODE_OF_CONDUCT.md already exists in the root, .github/,
    or docs/ directory.
    """

    check_id = "OSS-CH-03"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        candidates = [
            "CODE_OF_CONDUCT.md",
            ".github/CODE_OF_CONDUCT.md",
            "docs/CODE_OF_CONDUCT.md",
        ]
        for c in candidates:
            p = repo_root / c
            if p.exists():
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="CODE_OF_CONDUCT.md already exists.",
                )
        target = repo_root / "CODE_OF_CONDUCT.md"
        tmpl_path = (
            Path(__file__).parent.parent.parent.parent
            / "skills"
            / "iw-oss-publish"
            / "templates"
            / "CODE_OF_CONDUCT.md.j2"
        )
        config = _load_config(repo_root)
        if tmpl_path.exists():
            context = {
                "company_brand": config.get("company_brand", "Innovation Ways"),
                "company_contact_email": config.get(
                    "company_contact_email", "info@innovation-ways.com"
                ),
                "coc_version": "2.1",
            }
            content = _render_jinja2(tmpl_path, context)
        else:
            coc_email = config.get("company_contact_email", "info@innovation-ways.com")
            content = dedent(f"""\
                # Contributor Covenant Code of Conduct

                ## Our Pledge

                We as members, contributors, and leaders pledge to make participation in our
                community a harassment-free experience for everyone.

                ## Our Standards

                Examples of behavior that contributes to a positive environment:

                * Using welcoming and inclusive language
                * Being respectful of differing viewpoints
                * Gracefully accepting constructive criticism

                ## Enforcement

                Instances of abusive, harassing, or otherwise unacceptable behavior may be
                reported to the community leadership responsible for enforcement.
                All complaints will be reviewed and investigated promptly and fairly.

                Report violations to: {coc_email}
                """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated from Contributor Covenant v2.1 template.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(CodeOfConductRecipe())


class ContributingRecipe:
    """Fix recipe that creates a CONTRIBUTING.md guide for contributors.

    Addresses OSS-CH-06: absence of documented contribution guidelines. Skips
    creation when CONTRIBUTING.md already exists in the root, .github/, or
    docs/ directory.
    """

    check_id = "OSS-CH-06"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        candidates = [
            "CONTRIBUTING.md",
            ".github/CONTRIBUTING.md",
            "docs/CONTRIBUTING.md",
        ]
        for c in candidates:
            p = repo_root / c
            if p.exists():
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="CONTRIBUTING.md already exists.",
                )
        target = repo_root / "CONTRIBUTING.md"
        tmpl_path = (
            Path(__file__).parent.parent.parent.parent
            / "skills"
            / "iw-oss-publish"
            / "templates"
            / "CONTRIBUTING.md.j2"
        )
        config = _load_config(repo_root)
        if tmpl_path.exists():
            context = {
                "project_name": config.get("project_name", repo_root.name),
                "company_brand": config.get("company_brand", "Innovation Ways"),
                "company_github_org": config.get("company_github_org", "innovation-ways"),
                "company_contact_email": config.get(
                    "company_contact_email", "info@innovation-ways.com"
                ),
                "contributor_agreement": config.get("contributor_agreement", "DCO"),
            }
            content = _render_jinja2(tmpl_path, context)
        else:
            content = dedent("""\
                # Contributing

                Thank you for your interest in contributing!

                ## Getting Started

                1. Fork the repository
                2. Create a feature branch (`git checkout -b feat/my-feature`)
                3. Make your changes
                4. Run tests (`make test`)
                5. Commit with sign-off (`git commit -s`)

                ## Sign-off Requirement

                All commits must include a Signed-Off-By line to certify the
                [Developer Certificate of Origin](https://developercertificate.org/):

                ```
                Signed-off-by: Your Name <your.email@example.com>
                ```

                ## Code Review

                We review contributions on a rolling basis. Responses typically within 48 hours.
                """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated from iw-oss-publish CONTRIBUTING template.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(ContributingRecipe())


class CodeownersRecipe:
    """Fix recipe that creates a .github/CODEOWNERS file.

    Addresses OSS-CH-08: absence of defined code ownership assignments. Skips
    creation when CODEOWNERS already exists in the root, .github/, or docs/
    directory.
    """

    check_id = "OSS-CH-08"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        candidates = ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]
        for c in candidates:
            p = repo_root / c
            if p.exists():
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="CODEOWNERS already exists.",
                )
        target = repo_root / ".github" / "CODEOWNERS"
        content = dedent("""\
            # CODEOWNERS
            # Define code ownership for this repository.

            # Default rule — requires approval from @innovation-ways/maintainers
            *       @innovation-ways/maintainers

            # Documentation
            docs/    @innovation-ways/docs
            *.md     @innovation-ways/docs

            # CI/CD
            .github/workflows/ @innovation-ways/ci
            """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated from iw-oss-publish CODEOWNERS template.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(CodeownersRecipe())


class PrTemplateRecipe:
    """Fix recipe that creates a GitHub pull request description template.

    Addresses OSS-CH-09: absence of a standardised PR template to guide
    contributor submissions.
    """

    check_id = "OSS-CH-09"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        candidates = [
            ".github/PULL_REQUEST_TEMPLATE.md",
            "PULL_REQUEST_TEMPLATE.md",
            "docs/PULL_REQUEST_TEMPLATE.md",
        ]
        for c in candidates:
            p = repo_root / c
            if p.exists():
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="PR template already exists.",
                )
        target = repo_root / ".github" / "PULL_REQUEST_TEMPLATE.md"
        content = dedent("""\
            ## Description

            <!-- Briefly describe what this PR does. -->

            ## Type of change

            - [ ] Bug fix
            - [ ] New feature
            - [ ] Breaking change
            - [ ] Documentation update

            ## Testing

            <!-- Describe how this was tested. -->

            ## Sign-off

            All commits must be signed off under the Developer Certificate of Origin (DCO).
            """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated PR template.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(PrTemplateRecipe())


class IssueTemplateRecipe:
    """Fix recipe that creates GitHub issue templates for bug reports and features.

    Addresses OSS-CH-10: absence of structured issue templates that guide
    contributors to provide the right information when filing issues.
    """

    check_id = "OSS-CH-10"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        target = repo_root / ".github" / "ISSUE_TEMPLATE"
        bug_path = target / "bug_report.yml"
        feature_path = target / "feature_request.yml"
        for c in [bug_path, feature_path]:
            if c.exists():
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="Issue templates already populated.",
                )
        bug_content = dedent("""\
            name: Bug Report
            description: Report a bug to help us improve
            labels: ["bug"]
            body:
              - type: markdown
                attributes:
                  value: "## Bug Report"
              - type: textarea
                id: description
                attributes:
                  label: Description
                  placeholder: Describe the bug
                validations:
                  required: true
              - type: textarea
                id: steps
                attributes:
                  label: Steps to Reproduce
                validations:
                  required: true
            """)
        feature_content = dedent("""\
            name: Feature Request
            description: Suggest an idea for this project
            labels: ["enhancement"]
            body:
              - type: markdown
                attributes:
                  value: "## Feature Request"
              - type: textarea
                id: description
                attributes:
                  label: Description
                  placeholder: Describe the feature
                validations:
                  required: true
            """)
        return FixPreview(
            target_files=[bug_path, feature_path],
            full_contents={bug_path: bug_content, feature_path: feature_content},
            diffs={},
            notes="Generated issue templates (bug + feature).",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(IssueTemplateRecipe())


class SupportRecipe:
    """Fix recipe that creates a SUPPORT.md file describing how to get help.

    Addresses OSS-CH-11: absence of documented support channels. Skips
    creation when SUPPORT.md already exists in the root, .github/, or docs/
    directory.
    """

    check_id = "OSS-CH-11"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        candidates = ["SUPPORT.md", ".github/SUPPORT.md", "docs/SUPPORT.md"]
        for c in candidates:
            p = repo_root / c
            if p.exists():
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="SUPPORT.md already exists.",
                )
        target = repo_root / "SUPPORT.md"
        tmpl_path = (
            Path(__file__).parent.parent.parent.parent
            / "skills"
            / "iw-oss-publish"
            / "templates"
            / "SUPPORT.md.j2"
        )
        config = _load_config(repo_root)
        if tmpl_path.exists():
            context = {
                "company_brand": config.get("company_brand", "Innovation Ways"),
                "company_contact_email": config.get(
                    "company_contact_email", "info@innovation-ways.com"
                ),
            }
            content = _render_jinja2(tmpl_path, context)
        else:
            gh_org = config.get("company_github_org", "innovation-ways")
            gh_url = f"https://github.com/{gh_org}/{repo_root.name}"
            content = dedent(f"""\
                # Support

                ## Getting Help

                If you have a question or need help, please:

                - Open a [GitHub Discussion]({gh_url}/discussions)
                - File an [Issue]({gh_url}/issues)

                For security concerns, see [SECURITY.md](SECURITY.md).

                ## Contributing

                See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute.
                """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated SUPPORT.md template.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(SupportRecipe())


class DcoSignoffRecipe:
    """Fix recipe that appends a DCO sign-off section to an existing CONTRIBUTING.md.

    Addresses OSS-CH-07: absence of a Developer Certificate of Origin sign-off
    requirement. Only modifies the file when DCO language is not already present;
    does nothing when CONTRIBUTING.md does not exist.
    """

    check_id = "OSS-CH-07"
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
                notes="CONTRIBUTING.md not found — cannot add DCO sign-off.",
            )
        text = target.read_text()
        if "signed-off-by" in text.lower() or "developer certificate of origin" in text.lower():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="DCO sign-off already mentioned in CONTRIBUTING.md.",
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


register(DcoSignoffRecipe())
