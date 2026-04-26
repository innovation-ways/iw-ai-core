"""OSS-ENV — Environment pre-flight."""

from __future__ import annotations

from lib.context import Context
from lib.registry import register
from lib.tools import missing_tier1
from lib.types import Finding, Severity, Status

DOMAIN = "environment"


@register(id_prefix="OSS-ENV", order=1, domain=DOMAIN)
def env_preflight(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    # OSS-ENV-01: git repo
    git_dir = ctx.target / ".git"
    out.append(
        Finding(
            id="OSS-ENV-01",
            severity=Severity.MUST,
            status=Status.PASS if git_dir.exists() else Status.FAIL,
            domain=DOMAIN,
            summary="Target is a git repository"
            if git_dir.exists()
            else "Target is NOT a git repository",
            auto_fix_available=False,
            auto_apply_safe=False,
        )
    )

    # OSS-ENV-02: Tier-1 tools installed
    missing = missing_tier1(ctx.tools)
    if not missing:
        out.append(
            Finding(
                id="OSS-ENV-02",
                severity=Severity.MUST,
                status=Status.PASS,
                domain=DOMAIN,
                summary="All Tier-1 tools installed",
                evidence={"tools": {t: v for t, v in ctx.tools.items() if v}},
                auto_apply_safe=False,
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-ENV-02",
                severity=Severity.MUST,
                status=Status.FAIL,
                domain=DOMAIN,
                summary=f"{len(missing)} Tier-1 tool(s) missing",
                detail="Missing: " + ", ".join(missing),
                remediation="Run `bash .claude/skills/iw-oss-publish/scripts/install_tools.sh`",
                evidence={"missing": missing},
                auto_apply_safe=False,
            )
        )

    # OSS-ENV-03: .iw/oss-publish.toml present
    iw_config = ctx.target / ".iw" / "oss-publish.toml"
    out.append(
        Finding(
            id="OSS-ENV-03",
            severity=Severity.SHOULD,
            status=Status.PASS if iw_config.exists() else Status.FAIL,
            domain=DOMAIN,
            summary=".iw/oss-publish.toml present"
            if iw_config.exists()
            else ".iw/oss-publish.toml missing — using skill defaults",
            remediation=None
            if iw_config.exists()
            else "`make_oss` will write a resolved config here.",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-ENV-04: .iw/ in .gitignore
    gi = ctx.target / ".gitignore"
    gi_content = gi.read_text(encoding="utf-8", errors="replace") if gi.exists() else ""
    has_iw_entry = any(line.strip().rstrip("/") == ".iw" for line in gi_content.splitlines())
    out.append(
        Finding(
            id="OSS-ENV-04",
            severity=Severity.MAY,
            status=Status.PASS if has_iw_entry else Status.FAIL,
            domain=DOMAIN,
            summary=".iw/ is in .gitignore" if has_iw_entry else ".iw/ not in .gitignore",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    return out
