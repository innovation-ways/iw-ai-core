"""Config loader: .iw/oss-publish.toml -> pyproject[tool.iw.oss-publish] -> defaults."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "project_name": "",  # filled from target dir basename if empty
    "project_description": "",
    "license": "Apache-2.0",
    "company_legal_name": "Innovation Ways - Unipessoal LDA",
    "company_brand": "Innovation Ways",
    "company_github_org": "innovation-ways",
    "company_contact_email": "info@innovation-ways.com",
    "homepage": "https://innovation-ways.com",
    "contributor_agreement": "DCO",
    "coc_version": "v3",
    "sbom_formats": ["spdx", "cyclonedx"],
    "internal_email_domains": ["innovation-ways.com"],
    "internal_fqdn_suffixes": [".internal", ".corp", ".local", ".lan", ".intranet"],
    "disable_gh_live_checks": False,
    "checks": {"disabled": [], "demoted": {}},
    "tools": {"disabled": {}, "override": {}},
    "history": {},
    "export_control": {},
    "trademark": {},
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge overlay into base; overlay wins for scalars, dicts recurse, lists replace."""
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def load_config(target: Path) -> dict[str, Any]:
    """Resolve effective config for a target repo."""
    cfg = dict(DEFAULTS)

    # Source 2 (lower precedence): [tool.iw.oss-publish] in pyproject.toml
    pyproject = target / "pyproject.toml"
    if pyproject.exists():
        parsed = _load_toml(pyproject)
        sub = parsed.get("tool", {}).get("iw", {}).get("oss-publish", {})
        if isinstance(sub, dict):
            cfg = _deep_merge(cfg, sub)

    # Source 1 (highest precedence): .iw/oss-publish.toml
    iw_config = target / ".iw" / "oss-publish.toml"
    if iw_config.exists():
        cfg = _deep_merge(cfg, _load_toml(iw_config))

    # Final default: project_name from basename
    if not cfg.get("project_name"):
        cfg["project_name"] = target.resolve().name

    return cfg
