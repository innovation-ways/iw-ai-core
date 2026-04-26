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


class OwDirConfigRecipe:
    check_id = "OSS-ENV-03"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        target = repo_root / ".iw" / "oss-publish.toml"
        if target.exists():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes=".iw/oss-publish.toml already exists.",
            )
        tmpl_path = (
            Path(__file__).parent.parent.parent.parent
            / "skills"
            / "iw-oss-publish"
            / "templates"
            / ".iw-oss-publish.toml.j2"
        )
        if tmpl_path.exists():
            context = {
                "project_name": repo_root.name,
                "project_description": "",
                "license": "Apache-2.0",
                "company_legal_name": "Innovation Ways - Unipessoal LDA",
                "company_brand": "Innovation Ways",
                "company_github_org": "innovation-ways",
                "company_contact_email": "info@innovation-ways.com",
                "homepage": f"https://github.com/innovation-ways/{repo_root.name}",
                "contributor_agreement": "DCO",
                "coc_version": "2.1",
            }
            content = _render_jinja2(tmpl_path, context)
        else:
            content = dedent(f"""\
                # iw-oss-publish resolved configuration
                project_name         = "{repo_root.name}"
                project_description  = ""
                license              = "Apache-2.0"
                company_legal_name   = "Innovation Ways - Unipessoal LDA"
                company_brand        = "Innovation Ways"
                company_github_org   = "innovation-ways"
                company_contact_email = "info@innovation-ways.com"
                homepage             = "https://github.com/innovation-ways/{repo_root.name}"
                contributor_agreement = "DCO"
                coc_version          = "2.1"
                sbom_formats         = ["spdx", "cyclonedx"]
                internal_email_domains = ["innovation-ways.com"]
                internal_fqdn_suffixes = [".internal", ".corp", ".local"]
                """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated .iw/oss-publish.toml from template.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(OwDirConfigRecipe())
