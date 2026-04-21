"""Fix registry — one function per auto-fixable check.

Each fix function:
  - Takes Context (already scanned; config resolved)
  - Reads current state of target repo
  - Applies its recipe (writes/edits files in working tree; does NOT commit)
  - Returns a FixResult describing what was done

All fixes are idempotent: re-running produces no-op or identical result.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .context import Context
from .render import Renderer

logger = logging.getLogger(__name__)

FixFn = Callable[[Context, Renderer, dict], "FixResult"]


@dataclass
class FixResult:
    check_id: str
    summary: str
    status: str = "applied"  # "applied" | "skipped" | "error"
    files_written: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    detail: str = ""


_FIXES: dict[str, FixFn] = {}


def register_fix(check_id: str) -> Callable[[FixFn], FixFn]:
    def decorator(fn: FixFn) -> FixFn:
        if check_id in _FIXES:
            raise RuntimeError(f"duplicate fix for {check_id}")
        _FIXES[check_id] = fn
        return fn

    return decorator


def available_fixes() -> set[str]:
    return set(_FIXES.keys())


def apply_fix(
    check_id: str, ctx: Context, renderer: Renderer, render_ctx: dict
) -> FixResult | None:
    fn = _FIXES.get(check_id)
    if fn is None:
        return None
    try:
        return fn(ctx, renderer, render_ctx)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fix %s raised: %s", check_id, exc)
        return FixResult(
            check_id=check_id,
            status="error",
            summary=f"fix raised {type(exc).__name__}",
            detail=str(exc),
        )


# ===========================================================================
# Helper utilities
# ===========================================================================


def _append_missing(path: Path, entries: list[str], header: str | None = None) -> list[str]:
    """Append entries to a file if not already present. Returns the entries added."""
    existing = (
        path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    )
    existing_set = {line.strip() for line in existing}
    added = [e for e in entries if e not in existing_set]
    if not added:
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    if content and not content.endswith("\n"):
        content += "\n"
    if header and not content.endswith(header + "\n"):
        content += f"\n# {header}\n"
    content += "\n".join(added) + "\n"
    path.write_text(content, encoding="utf-8")
    return added


def _write_from_template(
    renderer: Renderer, template: str, dest: Path, render_ctx: dict, overwrite: bool = False
) -> bool:
    """Return True if file was written, False if it already existed."""
    return renderer.render_to_file(template, dest, render_ctx, overwrite=overwrite)


# ===========================================================================
# Fix implementations
# ===========================================================================


@register_fix("OSS-ENV-04")
def fix_iw_gitignore(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    gi = ctx.target / ".gitignore"
    added = _append_missing(gi, [".iw/"])
    if added:
        return FixResult("OSS-ENV-04", "Added .iw/ to .gitignore", files_modified=[".gitignore"])
    return FixResult("OSS-ENV-04", ".iw/ already in .gitignore", status="skipped")


@register_fix("OSS-HYG-01")
def fix_secret_gitignore(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    patterns = [".env", "*.pem", "*.key", "*.pfx", "*.p12"]
    gi = ctx.target / ".gitignore"
    added = _append_missing(gi, patterns, header="iw-oss-publish: secret hygiene")
    if added:
        return FixResult(
            "OSS-HYG-01",
            f"Added {len(added)} secret pattern(s) to .gitignore",
            files_modified=[".gitignore"],
            detail=", ".join(added),
        )
    return FixResult("OSS-HYG-01", "Secret patterns already in .gitignore", status="skipped")


@register_fix("OSS-HYG-03")
def fix_language_gitignore(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    """Append per-ecosystem .gitignore stanzas."""
    stanzas = {
        "python": [
            "__pycache__/",
            ".venv/",
            "*.pyc",
            ".pytest_cache/",
            ".mypy_cache/",
            ".ruff_cache/",
        ],
        "node": ["node_modules/", "npm-debug.log*", ".pnpm-store/"],
        "go": [],
        "rust": ["target/"],
        "java": ["target/", "build/", ".gradle/"],
    }
    gi = ctx.target / ".gitignore"
    added_all: list[str] = []
    for eco in ctx.ecosystems:
        entries = stanzas.get(eco, [])
        if not entries:
            continue
        added = _append_missing(gi, entries, header=f"iw-oss-publish: {eco} ignores")
        added_all.extend(added)
    if added_all:
        return FixResult(
            "OSS-HYG-03",
            f"Added {len(added_all)} language ignore(s)",
            files_modified=[".gitignore"],
        )
    return FixResult("OSS-HYG-03", "Language ignores already present", status="skipped")


@register_fix("OSS-SEC-04")
def fix_gitleaks_config(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / ".gitleaks.toml"
    written = _write_from_template(renderer, "gitleaks.toml.j2", dest, render_ctx)
    if written:
        return FixResult("OSS-SEC-04", "Wrote .gitleaks.toml", files_written=[".gitleaks.toml"])
    return FixResult("OSS-SEC-04", ".gitleaks.toml already present", status="skipped")


@register_fix("OSS-CI-06")
def fix_codeql_workflow(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / ".github" / "workflows" / "codeql.yml"
    written = _write_from_template(renderer, ".github/workflows/codeql.yml.j2", dest, render_ctx)
    path = ".github/workflows/codeql.yml"
    return FixResult(
        "OSS-CI-06",
        f"Wrote {path}" if written else f"{path} already present",
        status="applied" if written else "skipped",
        files_written=[path] if written else [],
    )


@register_fix("OSS-CI-07")
def fix_scorecard_workflow(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / ".github" / "workflows" / "scorecard.yml"
    written = _write_from_template(renderer, ".github/workflows/scorecard.yml", dest, render_ctx)
    path = ".github/workflows/scorecard.yml"
    return FixResult(
        "OSS-CI-07",
        f"Wrote {path}" if written else f"{path} already present",
        status="applied" if written else "skipped",
        files_written=[path] if written else [],
    )


@register_fix("OSS-CI-08")
def fix_dependabot(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / ".github" / "dependabot.yml"
    written = _write_from_template(renderer, ".github/dependabot.yml.j2", dest, render_ctx)
    path = ".github/dependabot.yml"
    return FixResult(
        "OSS-CI-08",
        f"Wrote {path}" if written else f"{path} already present",
        status="applied" if written else "skipped",
        files_written=[path] if written else [],
    )


@register_fix("OSS-CI-09")
def fix_compliance_workflow(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / ".github" / "workflows" / "compliance-scan.yml"
    written = _write_from_template(
        renderer, ".github/workflows/compliance-scan.yml", dest, render_ctx
    )
    path = ".github/workflows/compliance-scan.yml"
    return FixResult(
        "OSS-CI-09",
        f"Wrote {path}" if written else f"{path} already present",
        status="applied" if written else "skipped",
        files_written=[path] if written else [],
    )


@register_fix("OSS-CI-02")
def fix_action_pinning(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    """Run `pinact run` to SHA-pin unpinned third-party actions."""
    wf_dir = ctx.target / ".github" / "workflows"
    if not wf_dir.exists() or not ctx.has_tool("pinact"):
        return FixResult(
            "OSS-CI-02", "No workflows or pinact unavailable — skipped", status="skipped"
        )
    try:
        r = subprocess.run(
            ["pinact", "run"],
            cwd=ctx.target,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        return FixResult("OSS-CI-02", "pinact invocation failed", status="error", detail=str(exc))
    if r.returncode == 0:
        return FixResult(
            "OSS-CI-02",
            "pinact run applied (workflow files rewritten if needed)",
            files_modified=[".github/workflows/*"],
            detail=(r.stdout or "").strip()[:500],
        )
    return FixResult(
        "OSS-CI-02",
        "pinact run returned non-zero",
        status="error",
        detail=(r.stderr or r.stdout or "").strip()[:500],
    )


@register_fix("OSS-DEP-06")
def fix_third_party_licenses(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    """Generate THIRD_PARTY_LICENSES.md from SBOM (syft-produced)."""
    sbom_path = ctx.iw_dir / "sbom.spdx.json"
    if not sbom_path.exists():
        return FixResult("OSS-DEP-06", "SBOM missing — re-run scan first", status="skipped")
    try:
        data = json.loads(sbom_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return FixResult("OSS-DEP-06", "SBOM unreadable", status="error", detail=str(exc))
    lines = [
        f"# Third-Party Licenses — {render_ctx.get('project_name', '(unnamed)')}",
        "",
        "Aggregated third-party license notices for dependencies of this project.",
        "Generated from SBOM; see `.iw/sbom.spdx.json`.",
        "",
        "---",
        "",
    ]
    packages = data.get("packages", [])
    by_license: dict[str, list[str]] = {}
    for pkg in packages:
        name = pkg.get("name", "?")
        version = pkg.get("versionInfo", "?")
        license_id = pkg.get("licenseConcluded") or pkg.get("licenseDeclared") or "NOASSERTION"
        if license_id == "NOASSERTION" and name in ("?",):
            continue
        by_license.setdefault(license_id, []).append(f"{name}@{version}")
    for license_id in sorted(by_license):
        lines.append(f"## {license_id}")
        lines.append("")
        for pkg in sorted(by_license[license_id]):
            lines.append(f"- {pkg}")
        lines.append("")
    dest = ctx.target / "THIRD_PARTY_LICENSES.md"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return FixResult(
        "OSS-DEP-06",
        f"Generated THIRD_PARTY_LICENSES.md ({sum(len(v) for v in by_license.values())} deps)",
        files_written=["THIRD_PARTY_LICENSES.md"],
    )


# ---- License / NOTICE / community files ----------------------------------


@register_fix("OSS-LIC-01")
def fix_license(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    license_id = render_ctx.get("license", "Apache-2.0")
    template = f"LICENSE-{license_id}"
    if not (
        renderer.env.loader.searchpath
        and (Path(renderer.env.loader.searchpath[0]) / template).exists()
    ):
        return FixResult(
            "OSS-LIC-01",
            f"No template for license '{license_id}'",
            status="error",
            detail="Supported: Apache-2.0, MIT. Edit .iw/oss-publish.toml to change.",
        )
    dest = ctx.target / "LICENSE"
    written = _write_from_template(renderer, template, dest, render_ctx)
    if written:
        return FixResult("OSS-LIC-01", f"Wrote LICENSE ({license_id})", files_written=["LICENSE"])
    return FixResult("OSS-LIC-01", "LICENSE already present", status="skipped")


@register_fix("OSS-LIC-06")
def fix_notice(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    if render_ctx.get("license") != "Apache-2.0":
        return FixResult(
            "OSS-LIC-06", "NOTICE only required for Apache-2.0; skipping", status="skipped"
        )
    dest = ctx.target / "NOTICE"
    written = _write_from_template(renderer, "NOTICE.j2", dest, render_ctx)
    if written:
        return FixResult("OSS-LIC-06", "Wrote NOTICE (Apache-2.0)", files_written=["NOTICE"])
    return FixResult("OSS-LIC-06", "NOTICE already present", status="skipped")


@register_fix("OSS-CH-01")
def fix_readme(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / "README.md"
    written = _write_from_template(renderer, "README.md.j2", dest, render_ctx)
    if written:
        return FixResult(
            "OSS-CH-01",
            "Wrote README.md stub (fill in Installation/Usage)",
            files_written=["README.md"],
        )
    return FixResult("OSS-CH-01", "README already present", status="skipped")


@register_fix("OSS-CH-02")
def fix_security(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / "SECURITY.md"
    written = _write_from_template(renderer, "SECURITY.md.j2", dest, render_ctx)
    if written:
        return FixResult("OSS-CH-02", "Wrote SECURITY.md", files_written=["SECURITY.md"])
    return FixResult("OSS-CH-02", "SECURITY.md already present", status="skipped")


@register_fix("OSS-CH-03")
def fix_code_of_conduct(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / "CODE_OF_CONDUCT.md"
    written = _write_from_template(renderer, "CODE_OF_CONDUCT.md.j2", dest, render_ctx)
    if written:
        return FixResult(
            "OSS-CH-03",
            f"Wrote CODE_OF_CONDUCT.md ({render_ctx.get('coc_version', 'v3')})",
            files_written=["CODE_OF_CONDUCT.md"],
        )
    return FixResult("OSS-CH-03", "CODE_OF_CONDUCT.md already present", status="skipped")


@register_fix("OSS-CH-06")
def fix_contributing(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / "CONTRIBUTING.md"
    written = _write_from_template(renderer, "CONTRIBUTING.md.j2", dest, render_ctx)
    if written:
        return FixResult(
            "OSS-CH-06",
            "Wrote CONTRIBUTING.md (with DCO sign-off section)",
            files_written=["CONTRIBUTING.md"],
        )
    return FixResult("OSS-CH-06", "CONTRIBUTING.md already present", status="skipped")


@register_fix("OSS-CH-08")
def fix_codeowners(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / ".github" / "CODEOWNERS"
    written = _write_from_template(renderer, "CODEOWNERS.j2", dest, render_ctx)
    if written:
        return FixResult(
            "OSS-CH-08", "Wrote .github/CODEOWNERS", files_written=[".github/CODEOWNERS"]
        )
    return FixResult("OSS-CH-08", "CODEOWNERS already present", status="skipped")


@register_fix("OSS-CH-09")
def fix_pr_template(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / ".github" / "PULL_REQUEST_TEMPLATE.md"
    written = _write_from_template(renderer, ".github/PULL_REQUEST_TEMPLATE.md", dest, render_ctx)
    if written:
        return FixResult(
            "OSS-CH-09",
            "Wrote .github/PULL_REQUEST_TEMPLATE.md",
            files_written=[".github/PULL_REQUEST_TEMPLATE.md"],
        )
    return FixResult("OSS-CH-09", "PR template already present", status="skipped")


@register_fix("OSS-CH-10")
def fix_issue_templates(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    written_files: list[str] = []
    for name in ("bug_report.yml", "feature_request.yml"):
        dest = ctx.target / ".github" / "ISSUE_TEMPLATE" / name
        if _write_from_template(renderer, f".github/ISSUE_TEMPLATE/{name}", dest, render_ctx):
            written_files.append(f".github/ISSUE_TEMPLATE/{name}")
    if written_files:
        return FixResult(
            "OSS-CH-10",
            f"Wrote {len(written_files)} issue template(s)",
            files_written=written_files,
        )
    return FixResult("OSS-CH-10", "Issue templates already present", status="skipped")


@register_fix("OSS-CH-11")
def fix_support(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / "SUPPORT.md"
    written = _write_from_template(renderer, "SUPPORT.md.j2", dest, render_ctx)
    if written:
        return FixResult("OSS-CH-11", "Wrote SUPPORT.md", files_written=["SUPPORT.md"])
    return FixResult("OSS-CH-11", "SUPPORT.md already present", status="skipped")


# ---- Trademark / contributor agreement / release-automation ---------------


@register_fix("OSS-TM-01")
def fix_trademark(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / "TRADEMARK.md"
    written = _write_from_template(renderer, "TRADEMARK.md.j2", dest, render_ctx)
    if written:
        return FixResult("OSS-TM-01", "Wrote TRADEMARK.md", files_written=["TRADEMARK.md"])
    return FixResult("OSS-TM-01", "TRADEMARK.md already present", status="skipped")


@register_fix("OSS-CA-01")
def fix_dco_config(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    if render_ctx.get("contributor_agreement", "DCO") != "DCO":
        return FixResult(
            "OSS-CA-01", "Config says CLA, not DCO — skipping DCO config", status="skipped"
        )
    dest = ctx.target / ".github" / "dco.yml"
    written = _write_from_template(renderer, ".github/dco.yml", dest, render_ctx)
    if written:
        return FixResult(
            "OSS-CA-01",
            "Wrote .github/dco.yml (install cncf/dco2 app on the org to activate)",
            files_written=[".github/dco.yml"],
        )
    return FixResult("OSS-CA-01", ".github/dco.yml already present", status="skipped")


@register_fix("OSS-REL-01")
def fix_changelog(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / "CHANGELOG.md"
    written = _write_from_template(renderer, "CHANGELOG.md.j2", dest, render_ctx)
    if written:
        return FixResult(
            "OSS-REL-01",
            "Wrote CHANGELOG.md (Keep-a-Changelog skeleton)",
            files_written=["CHANGELOG.md"],
        )
    return FixResult("OSS-REL-01", "CHANGELOG.md already present", status="skipped")


@register_fix("OSS-REL-03")
def fix_release_please(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / ".github" / "workflows" / "release-please.yml"
    written = _write_from_template(
        renderer, ".github/workflows/release-please.yml.j2", dest, render_ctx
    )
    path = ".github/workflows/release-please.yml"
    if written:
        return FixResult("OSS-REL-03", f"Wrote {path}", files_written=[path])
    return FixResult("OSS-REL-03", "release-please.yml already present", status="skipped")


@register_fix("OSS-ENV-03")
def fix_resolved_config(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / ".iw" / "oss-publish.toml"
    written = _write_from_template(renderer, ".iw-oss-publish.toml.j2", dest, render_ctx)
    if written:
        return FixResult(
            "OSS-ENV-03",
            "Wrote .iw/oss-publish.toml (resolved config)",
            files_written=[".iw/oss-publish.toml"],
        )
    return FixResult("OSS-ENV-03", ".iw/oss-publish.toml already present", status="skipped")


# ---- Pre-commit config ----------------------------------------------------


@register_fix("PRE-COMMIT-CONFIG")  # synthetic id; not a standard check
def fix_pre_commit_config(ctx: Context, renderer: Renderer, render_ctx: dict) -> FixResult:
    dest = ctx.target / ".pre-commit-config.yaml"
    written = _write_from_template(renderer, ".pre-commit-config.yaml.j2", dest, render_ctx)
    if written:
        return FixResult(
            "PRE-COMMIT-CONFIG",
            "Wrote .pre-commit-config.yaml",
            files_written=[".pre-commit-config.yaml"],
        )
    return FixResult(
        "PRE-COMMIT-CONFIG", ".pre-commit-config.yaml already present", status="skipped"
    )
