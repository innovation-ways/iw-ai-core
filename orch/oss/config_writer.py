"""Write .iw/oss-publish.toml for a project."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from orch.config import CORE_ROOT


class ConfigFileExistsError(Exception):
    """Raised when the target config file already exists with differing content."""


def write_project_config(project: Project, *, force: bool = False) -> Path:
    """Write the .iw/oss-publish.toml configuration file for a project.

    Renders the config from the iw-oss-publish Jinja2 template if available,
    falling back to an inline default template. Skips writing when the file
    already exists with identical content.

    Args:
        project: Project whose repo_root receives the config file.
        force: When True, overwrite an existing file that differs from the
            rendered content. When False, raise ConfigFileExistsError instead.

    Returns:
        Path to the written (or unchanged) config file.

    Raises:
        ConfigFileExistsError: If the config file exists with different content
            and force is False.
    """
    repo_root = Path(project.repo_root)
    iw_dir = repo_root / ".iw"
    config_path = iw_dir / "oss-publish.toml"

    template_path = (
        CORE_ROOT
        / ".claude"
        / "skills"
        / "iw-oss-publish"
        / "templates"
        / ".iw-oss-publish.toml.j2"
    )

    if template_path.exists():
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        template_dir = template_path.parent
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(),
        )
        template = env.get_template(".iw-oss-publish.toml.j2")
        rendered = template.render(
            project_name=project.display_name or project.id,
            project_description="",
            license="Apache-2.0",
            company_legal_name="Innovation Ways - Unipessoal LDA",
            company_brand="Innovation Ways",
            company_github_org="innovation-ways",
            company_contact_email="info@innovation-ways.com",
            homepage="https://innovation-ways.com",
            contributor_agreement="DCO",
            coc_version="v3",
        )
    else:
        rendered = _render_inline_config(project)

    if config_path.exists():
        if config_path.read_text() == rendered:
            return config_path
        if not force:
            msg = (
                f"Config file already exists and differs: {config_path} "
                "(pass force=True to overwrite)"
            )
            raise ConfigFileExistsError(msg)

    iw_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(rendered)
    return config_path


def _render_inline_config(project: Project) -> str:
    """Render a default oss-publish.toml content string without a Jinja2 template.

    Used as a fallback when the iw-oss-publish skill template file is not present.
    Produces a fully commented TOML with sensible Innovation Ways defaults.

    Args:
        project: Project whose display_name (or id) is embedded in the output.

    Returns:
        Rendered TOML string ready to write to disk.
    """
    pn = project.display_name or project.id
    return dedent(f"""\
        # iw-oss-publish resolved configuration
        # Written once by `iw-oss-publish make_oss`; edit as needed for subsequent runs.
        # Location: .iw/oss-publish.toml

        project_name         = "{pn}"
        project_description  = ""
        license              = "Apache-2.0"
        company_legal_name   = "Innovation Ways - Unipessoal LDA"
        company_brand        = "Innovation Ways"
        company_github_org   = "innovation-ways"
        company_contact_email = "info@innovation-ways.com"
        homepage             = "https://innovation-ways.com"
        contributor_agreement = "DCO"
        coc_version          = "v3"
        sbom_formats         = ["spdx", "cyclonedx"]
        internal_email_domains = ["innovation-ways.com"]
        internal_fqdn_suffixes = [".internal", ".corp", ".local", ".lan", ".intranet"]

        [history]
        # strategy = "nuke"  # nuke | filter-repo | preserve
        # decided_at = ""
        # rationale = ""

        [export_control]
        # standard_crypto_only = true
        # non_standard_crypto_notified = false

        [trademark]
        # uspto_searched = "YYYY-MM-DD"
        # wipo_searched  = "YYYY-MM-DD"
        # name_collision_accepted = []

        [checks]
        # disabled = []
        # demoted = {{ }}

        [tools]
        # disabled = {{ }}
        # override = {{ }}
    """)


class Project:
    """Minimal project descriptor used by the config writer.

    Attributes:
        id: Unique project identifier used as a fallback display name.
        display_name: Human-readable project name; may be None.
        repo_root: Absolute filesystem path to the project repository root.
    """

    id: str
    display_name: str | None
    repo_root: str
