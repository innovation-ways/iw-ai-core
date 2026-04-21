"""OSS-CA — Contributor agreement (DCO / CLA)."""

from __future__ import annotations

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "contributor_agreement"


@register(id_prefix="OSS-CA", order=13, domain=DOMAIN)
def contributor_agreement(ctx: Context) -> list[Finding]:
    out: list[Finding] = []
    mode_cfg = ctx.config.get("contributor_agreement", "DCO")

    # OSS-CA-01: DCO / CLA configured
    dco_cfg = ctx.exists(".github/dco.yml")
    cla_cfg = ctx.exists(".github/cla.yml", "CLA.md")
    if mode_cfg == "DCO":
        if dco_cfg:
            out.append(
                Finding(
                    id="OSS-CA-01",
                    severity=Severity.SHOULD,
                    status=Status.PASS,
                    domain=DOMAIN,
                    summary=f"DCO config present at {dco_cfg}",
                )
            )
        else:
            out.append(
                Finding(
                    id="OSS-CA-01",
                    severity=Severity.SHOULD,
                    status=Status.FAIL,
                    domain=DOMAIN,
                    summary=".github/dco.yml missing",
                    remediation=(
                        "`make_oss` renders dco.yml. Also install the CNCF DCO app on the org: "
                        "https://github.com/apps/dco"
                    ),
                    auto_fix_available=True,
                )
            )
    else:
        out.append(
            Finding(
                id="OSS-CA-01",
                severity=Severity.SHOULD,
                status=Status.PASS if cla_cfg else Status.HUMAN_REQUIRED,
                domain=DOMAIN,
                summary=f"CLA config present at {cla_cfg}"
                if cla_cfg
                else "CLA configured in config but no CLA file found",
                remediation="Add CLA document and configure cla-assistant or EasyCLA."
                if not cla_cfg
                else None,
            )
        )

    # OSS-CA-02: CONTRIBUTING references sign-off (reuses OSS-CH-07 detection, reported here with context)
    contributing = ctx.exists("CONTRIBUTING.md", ".github/CONTRIBUTING.md")
    if contributing and mode_cfg == "DCO":
        body = (ctx.read_text(contributing) or "").lower()
        has_signoff = ("signed-off-by" in body) or ("git commit -s" in body)
        out.append(
            Finding(
                id="OSS-CA-02",
                severity=Severity.SHOULD,
                status=Status.PASS if has_signoff else Status.FAIL,
                domain=DOMAIN,
                summary="CONTRIBUTING explains DCO sign-off"
                if has_signoff
                else "CONTRIBUTING does not explain sign-off",
                auto_fix_available=True,
            )
        )

    # OSS-CA-03: branch protection requires dco check (gh live)
    if ctx.has_tool("gh") and ctx.repo.has_remote:
        # Will be revisited in OSS-GH checks; stub as SKIP here to avoid double-reporting
        out.append(
            Finding(
                id="OSS-CA-03",
                severity=Severity.SHOULD,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="Branch-protection DCO check verified under OSS-GH-01",
                osps_control="OSPS-AC-03.01",
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-CA-03",
                severity=Severity.SHOULD,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="Branch-protection check needs gh CLI + remote",
            )
        )

    return out
