"""Template rendering for make_oss mode.

Loads templates from `skills/iw-oss-publish/templates/` and renders them with
the resolved project config as the Jinja2 context.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, Undefined
except ImportError as exc:  # pragma: no cover — handled by install_tools.sh
    raise RuntimeError(
        "jinja2 is required for make_oss mode. "
        "Run: bash .claude/skills/iw-oss-publish/scripts/install_tools.sh"
    ) from exc


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def templates_dir() -> Path:
    """Path to the bundled templates directory."""
    # lib/render.py → lib/ → scripts/ → iw-oss-publish/ → templates/
    return Path(__file__).resolve().parent.parent.parent / "templates"


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

LICENSE_BADGE_SLUGS = {
    "Apache-2.0": "Apache_2.0-blue",
    "MIT": "MIT-yellow",
    "BSD-3-Clause": "BSD_3--Clause-orange",
    "ISC": "ISC-green",
    "0BSD": "0BSD-lightgrey",
}


def build_render_context(
    config: dict[str, Any], ecosystems: set[str] | None = None
) -> dict[str, Any]:
    """Produce the dict passed to Jinja2 when rendering any template."""
    ecosystems = ecosystems or set()
    year = datetime.date.today().year

    ctx = dict(config)
    ctx.setdefault("year", year)
    ctx.setdefault(
        "license_badge_slug",
        LICENSE_BADGE_SLUGS.get(config.get("license", "Apache-2.0"), "custom-lightgrey"),
    )
    ctx["ecosystem_python"] = "python" in ecosystems
    ctx["ecosystem_node"] = "node" in ecosystems
    ctx["ecosystem_go"] = "go" in ecosystems
    ctx["ecosystem_rust"] = "rust" in ecosystems
    ctx["ecosystem_docker"] = "docker" in ecosystems
    ctx["ecosystem_java"] = "java" in ecosystems

    # Contributor Covenant version paths for the CoC template.
    coc_version = config.get("coc_version", "v3")
    version_path_map = {"v3": "3/0", "v2.1": "2/1", "v2.0": "2/0"}
    ctx["coc_version_path"] = version_path_map.get(coc_version, "3/0")

    # Compose internal_email_domains_regex for gitleaks.toml.j2
    domains = config.get("internal_email_domains", [])
    ctx["internal_email_domains_regex"] = (
        "|".join(d.replace(".", r"\.") for d in domains) if domains else ""
    )

    # CodeQL language mapping (for codeql.yml.j2 matrix)
    codeql_language_map = {
        "python": "python",
        "node": "javascript-typescript",
        "go": "go",
        "rust": None,  # no CodeQL support
        "java": "java-kotlin",
    }
    codeql_langs = sorted(
        {codeql_language_map[eco] for eco in ecosystems if codeql_language_map.get(eco)}
    )
    ctx["codeql_languages"] = ", ".join(codeql_langs) if codeql_langs else "python"

    # Release-please release-type per primary ecosystem
    release_type_map = {
        "python": "python",
        "node": "node",
        "go": "go",
        "rust": "rust",
        "java": "maven",
    }
    primary_eco = next(
        (e for e in ["python", "node", "go", "rust", "java"] if e in ecosystems), "simple"
    )
    ctx["release_please_type"] = release_type_map.get(primary_eco, "simple")

    return ctx


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class Renderer:
    """Wraps a Jinja2 Environment bound to the skill's template tree."""

    def __init__(self, *, strict: bool = False) -> None:
        loader = FileSystemLoader(str(templates_dir()))
        undefined: type[Undefined] = StrictUndefined if strict else Undefined
        self.env = Environment(
            loader=loader,
            undefined=undefined,
            keep_trailing_newline=True,
            autoescape=False,  # templates are for configs/markdown, not HTML
            trim_blocks=False,
            lstrip_blocks=False,
        )
        # Provide a 'quote' filter for templates that use it (e.g., TRADEMARK.md.j2)
        self.env.filters.setdefault("quote", lambda s: f'"{s}"')

    def render(self, template_path: str, context: dict[str, Any]) -> str:
        """Render a template by path relative to templates/.

        `template_path` may end with `.j2` or not — .j2 is canonical for Jinja templates.
        """
        template = self.env.get_template(template_path)
        return template.render(**context)

    def render_to_file(
        self,
        template_path: str,
        dest: Path,
        context: dict[str, Any],
        overwrite: bool = False,
    ) -> bool:
        """Render a template and write to dest. Returns True if written, False if skipped."""
        if dest.exists() and not overwrite:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self.render(template_path, context), encoding="utf-8")
        return True
