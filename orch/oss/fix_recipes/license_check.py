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


class LicenseFileRecipe:
    check_id = "OSS-LIC-01"
    auto_apply_safe = True

    LICENSE_MAP = {
        "Apache-2.0": "LICENSE-Apache-2.0",
        "MIT": "LICENSE-MIT",
    }

    def preview(self, repo_root: Path) -> FixPreview:
        candidates = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md"]
        for c in candidates:
            if (repo_root / c).exists():
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="LICENSE already exists.",
                )
        config = _load_config(repo_root)
        license_type = config.get("license", "Apache-2.0")
        tmpl_name = self.LICENSE_MAP.get(license_type, "LICENSE-Apache-2.0")
        tmpl_path = (
            Path(__file__).parent.parent.parent.parent
            / "skills"
            / "iw-oss-publish"
            / "templates"
            / tmpl_name
        )
        if tmpl_path.exists():
            content = tmpl_path.read_text()
        else:
            legal_name = config.get("company_legal_name", "Innovation Ways - Unipessoal LDA")
            content = dedent(f"""\
                Apache License
                Version 2.0, January 2004
                http://www.apache.org/licenses/

                Copyright {2026} {legal_name}

                Licensed under the Apache License, Version 2.0 (the "License");
                you may not use this file except in compliance with the License.
                """)
        target = repo_root / "LICENSE"
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes=f"Generated {license_type} license file from template.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(LicenseFileRecipe())


class CopyrightYearRecipe:
    check_id = "OSS-LIC-05"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        candidates = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md"]
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
                notes="LICENSE file not found.",
            )
        text = target.read_text()
        import re

        years_in_text = [int(m.group()) for m in re.finditer(r"\b(19|20)\d{2}\b", text)]
        current_year = 2026
        if years_in_text and max(years_in_text) >= current_year - 1:
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="Copyright year is already current.",
            )
        new_text = re.sub(
            r"\b(20\d{2})(-\d{4})?",
            lambda m: f"{m.group(1)}-{{year}}".format(year=current_year),
            text,
            count=1,
        )
        if new_text == text:
            new_text = (
                text.rstrip() + f"\n\nCopyright (c) {current_year} Innovation Ways - Unipessoal LDA"
            )
        import difflib

        diff = "".join(difflib.unified_diff(text.splitlines(), new_text.splitlines(), lineterm=""))
        return FixPreview(
            target_files=[target],
            full_contents={},
            diffs={target: diff},
            notes=f"Updated copyright year to {current_year}.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        if not preview.target_files:
            return preview
        target = preview.target_files[0]
        text = target.read_text()
        import re

        years_in_text = [int(m.group()) for m in re.finditer(r"\b(19|20)\d{2}\b", text)]
        current_year = 2026
        if years_in_text and max(years_in_text) >= current_year - 1:
            return preview
        new_text = re.sub(
            r"\b(20\d{2})(-\d{4})?",
            lambda m: f"{m.group(1)}-{current_year}",
            text,
            count=1,
        )
        if new_text == text:
            new_text = (
                text.rstrip() + f"\n\nCopyright (c) {current_year} Innovation Ways - Unipessoal LDA"
            )
        target.write_text(new_text)
        return preview


register(CopyrightYearRecipe())


class NoticeFileRecipe:
    check_id = "OSS-LIC-06"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        candidates = ["NOTICE", "NOTICE.md", "NOTICE.txt"]
        for c in candidates:
            if (repo_root / c).exists():
                return FixPreview(
                    target_files=[],
                    full_contents={},
                    diffs={},
                    notes="NOTICE already exists.",
                )
        target = repo_root / "NOTICE"
        tmpl_path = (
            Path(__file__).parent.parent.parent.parent
            / "skills"
            / "iw-oss-publish"
            / "templates"
            / "NOTICE.j2"
        )
        config = _load_config(repo_root)
        if tmpl_path.exists():
            context = {
                "project_name": config.get("project_name", repo_root.name),
                "company_legal_name": config.get(
                    "company_legal_name", "Innovation Ways - Unipessoal LDA"
                ),
                "year": "2026",
            }
            content = _render_jinja2(tmpl_path, context)
        else:
            legal_name = config.get("company_legal_name", "Innovation Ways - Unipessoal LDA")
            content = dedent(f"""\
                # Third-Party Notices

                This project includes software developed by third parties.

                ## Innovation Ways

                Copyright {2026} {legal_name}.
                All rights reserved.
                """)
        return FixPreview(
            target_files=[target],
            full_contents={target: content},
            diffs={},
            notes="Generated NOTICE file for Apache-2.0 projects.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        for path, content in preview.full_contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return preview


register(NoticeFileRecipe())
