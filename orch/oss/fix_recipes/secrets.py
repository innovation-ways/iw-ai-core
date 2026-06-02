"""Fix recipes for secret scanning compliance checks (OSS-SEC-*)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any

from . import register
from .base import FixPreview


def _render_jinja2(template_path: Path, context: dict[str, Any]) -> str:
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        loader = FileSystemLoader(str(template_path.parent))
        env = Environment(loader=loader, autoescape=select_autoescape())
        template = env.get_template(template_path.name)
        return template.render(**context)
    except Exception:
        return ""


class GitleaksConfigRecipe:
    """Fix recipe that creates a .gitleaks.toml configuration file.

    Addresses OSS-SEC-04: absence of a gitleaks rule set for secret scanning.
    Uses the iw-oss-publish Jinja2 template when available; falls back to an
    inline stub covering AWS keys, generic API keys, and private key headers.
    """

    check_id = "OSS-SEC-04"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        target = repo_root / ".gitleaks.toml"
        if target.exists():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes=".gitleaks.toml exists.",
            )
        tmpl_path = (
            Path(__file__).parent.parent.parent.parent
            / "skills"
            / "iw-oss-publish"
            / "templates"
            / "gitleaks.toml.j2"
        )
        if tmpl_path.exists():
            content = _render_jinja2(tmpl_path, {})
        else:
            content = dedent("""\
                [rules]
                [rules.aws-access-key]
                description = "AWS Access Key"
                regex = '''(A3T[A-Z0-9]|AKIA|ASIA)[A-Z0-9]{16}'''
                tags = ["aws", "key"]

                [rules.generic-api-key]
                description = "Generic API Key"
                regex = '''(?i)(api[_-]?key|apikey|secret[_-]?key|
                    auth_token|access[_-]?token)['\"]?[:=]\\s*['\"]?[a-zA-Z0-9]{16,}'''
                tags = ["api-key", "secret"]

                [rules.private-key]
                description = "Private Key"
                regex = '''-----BEGIN (RSA |DSA |EC |OPENSSH )PRIVATE KEY-----'''
                tags = ["key", "crypto"]

                [rules.dco]
                description = "DCO sign-off"
                regex = '''Signed-off-by: .+'''
                allowlist = true
                tags = ["dco"]

                [allowlist]
                repos = []
                """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated .gitleaks.toml with IW rules.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.write_text(content)
        return preview


register(GitleaksConfigRecipe())


class DetectSecretsBaselineRecipe:
    """Fix recipe that creates an empty detect-secrets baseline file.

    Addresses OSS-SEC-05: absence of a .secrets.baseline file used by the
    detect-secrets tool to track and suppress known false positives. The
    generated baseline is empty; operators should run ``detect-secrets audit``
    to populate it.
    """

    check_id = "OSS-SEC-05"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        target = repo_root / ".secrets.baseline"
        if target.exists():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes=".secrets.baseline exists.",
            )
        content = dedent("""\
            {
              "version": "1.1.0",
              "plugins_used": [
                {
                  "name": "DetectorInstaller"
                }
              ],
              "results_expected": {},
              "metrics": {
                "count": 0,
                "last_commit_hash": ""
              }
            }
            """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated detect-secrets baseline (run `detect-secrets audit` to populate).",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.write_text(content)
        return preview


register(DetectSecretsBaselineRecipe())
