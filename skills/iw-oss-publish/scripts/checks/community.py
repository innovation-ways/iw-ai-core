"""OSS-CH — Community health files."""

from __future__ import annotations

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "community"


@register(id_prefix="OSS-CH", order=9, domain=DOMAIN)
def community(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    # OSS-CH-01: README
    readme = ctx.exists("README.md", "README.rst", "README.txt", "README")
    out.append(
        Finding(
            id="OSS-CH-01",
            severity=Severity.MUST,
            status=Status.PASS if readme else Status.FAIL,
            domain=DOMAIN,
            summary=f"README present at {readme}" if readme else "README missing",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-CH-02: SECURITY.md
    security = ctx.exists("SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md")
    if security:
        sec_text = (ctx.read_text(security) or "").lower()
        has_reporting = ("report" in sec_text) and ("@" in sec_text or "advisories" in sec_text)
        out.append(
            Finding(
                id="OSS-CH-02",
                severity=Severity.MUST,
                status=Status.PASS if has_reporting else Status.HUMAN_REQUIRED,
                domain=DOMAIN,
                summary=f"SECURITY.md at {security} (reporting path present)"
                if has_reporting
                else f"SECURITY.md at {security} missing clear reporting instructions",
                remediation="Ensure a reporting email or GitHub Security Advisories link is included."
                if not has_reporting
                else None,
                osps_control="OSPS-VM-02.01",
                auto_fix_available=True,
                auto_apply_safe=False,
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-CH-02",
                severity=Severity.MUST,
                status=Status.FAIL,
                domain=DOMAIN,
                summary="SECURITY.md missing",
                remediation="`make_oss` renders from template.",
                osps_control="OSPS-VM-02.01",
                auto_fix_available=True,
                auto_apply_safe=True,
            )
        )

    # OSS-CH-03: CODE_OF_CONDUCT.md
    coc = ctx.exists("CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md", "docs/CODE_OF_CONDUCT.md")
    out.append(
        Finding(
            id="OSS-CH-03",
            severity=Severity.SHOULD,
            status=Status.PASS if coc else Status.FAIL,
            domain=DOMAIN,
            summary=f"CODE_OF_CONDUCT at {coc}" if coc else "CODE_OF_CONDUCT missing",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-CH-04: Contributor Covenant v2.1+
    if coc:
        coc_text = ctx.read_text(coc) or ""
        # Accept anything v2.1, v2.2, v3, etc.
        has_v3 = "version/3" in coc_text or "Contributor Covenant 3" in coc_text
        has_v21_or_newer = any(
            s in coc_text
            for s in (
                "version/2/1",
                "version/3",
                "Contributor Covenant 2.1",
                "Contributor Covenant 3",
            )
        )
        if has_v3:
            out.append(
                Finding(
                    id="OSS-CH-04",
                    severity=Severity.SHOULD,
                    status=Status.PASS,
                    domain=DOMAIN,
                    summary="Contributor Covenant v3 in use",
                    auto_apply_safe=False,
                )
            )
        elif has_v21_or_newer:
            out.append(
                Finding(
                    id="OSS-CH-04",
                    severity=Severity.SHOULD,
                    status=Status.PASS,
                    domain=DOMAIN,
                    summary="Contributor Covenant v2.1 (acceptable — v3 recommended)",
                    auto_apply_safe=False,
                )
            )
        else:
            out.append(
                Finding(
                    id="OSS-CH-04",
                    severity=Severity.SHOULD,
                    status=Status.HUMAN_REQUIRED,
                    domain=DOMAIN,
                    summary="CoC present but Contributor Covenant version undetected",
                    remediation="Verify CoC references v2.1 or v3 explicitly.",
                    auto_apply_safe=False,
                )
            )

    # OSS-CH-05: enforcement contact is a group email
    if coc:
        coc_text = ctx.read_text(coc) or ""
        group_email = ctx.config.get("company_contact_email", "info@innovation-ways.com")
        has_group_email = group_email in coc_text
        out.append(
            Finding(
                id="OSS-CH-05",
                severity=Severity.SHOULD,
                status=Status.PASS if has_group_email else Status.HUMAN_REQUIRED,
                domain=DOMAIN,
                summary=f"CoC enforcement contact references {group_email}"
                if has_group_email
                else f"CoC enforcement contact does not reference {group_email}",
                remediation="Use a group/alias email instead of a personal address."
                if not has_group_email
                else None,
                auto_apply_safe=False,
            )
        )

    # OSS-CH-06: CONTRIBUTING.md
    contributing = ctx.exists("CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md")
    out.append(
        Finding(
            id="OSS-CH-06",
            severity=Severity.SHOULD,
            status=Status.PASS if contributing else Status.FAIL,
            domain=DOMAIN,
            summary=f"CONTRIBUTING at {contributing}" if contributing else "CONTRIBUTING missing",
            osps_control="OSPS-GV-03.01",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-CH-07: CONTRIBUTING references DCO sign-off
    if contributing and ctx.config.get("contributor_agreement", "DCO") == "DCO":
        body = (ctx.read_text(contributing) or "").lower()
        has_dco = (
            ("signed-off-by" in body)
            or ("git commit -s" in body)
            or ("developer certificate of origin" in body)
        )
        out.append(
            Finding(
                id="OSS-CH-07",
                severity=Severity.SHOULD,
                status=Status.PASS if has_dco else Status.FAIL,
                domain=DOMAIN,
                summary="CONTRIBUTING explains DCO sign-off"
                if has_dco
                else "CONTRIBUTING does not mention DCO sign-off",
                auto_fix_available=True,
                auto_apply_safe=True,
            )
        )

    # OSS-CH-08: CODEOWNERS
    codeowners = ctx.exists("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")
    out.append(
        Finding(
            id="OSS-CH-08",
            severity=Severity.SHOULD,
            status=Status.PASS if codeowners else Status.FAIL,
            domain=DOMAIN,
            summary=f"CODEOWNERS at {codeowners}" if codeowners else "CODEOWNERS missing",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-CH-09: PR template
    pr_tpl = ctx.exists(
        ".github/PULL_REQUEST_TEMPLATE.md",
        "PULL_REQUEST_TEMPLATE.md",
        "docs/PULL_REQUEST_TEMPLATE.md",
    )
    out.append(
        Finding(
            id="OSS-CH-09",
            severity=Severity.SHOULD,
            status=Status.PASS if pr_tpl else Status.FAIL,
            domain=DOMAIN,
            summary=f"PR template at {pr_tpl}" if pr_tpl else "PR template missing",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-CH-10: issue templates
    issue_dir = ctx.target / ".github" / "ISSUE_TEMPLATE"
    has_issue_tpl = issue_dir.is_dir() and any(issue_dir.iterdir())
    out.append(
        Finding(
            id="OSS-CH-10",
            severity=Severity.SHOULD,
            status=Status.PASS if has_issue_tpl else Status.FAIL,
            domain=DOMAIN,
            summary=".github/ISSUE_TEMPLATE populated"
            if has_issue_tpl
            else "No issue templates at .github/ISSUE_TEMPLATE/",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-CH-11: SUPPORT.md
    support = ctx.exists("SUPPORT.md", ".github/SUPPORT.md", "docs/SUPPORT.md")
    out.append(
        Finding(
            id="OSS-CH-11",
            severity=Severity.MAY,
            status=Status.PASS if support else Status.FAIL,
            domain=DOMAIN,
            summary=f"SUPPORT at {support}" if support else "SUPPORT.md not present (optional)",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-CH-12: FUNDING.yml
    funding = ctx.exists(".github/FUNDING.yml", ".github/funding.yml")
    out.append(
        Finding(
            id="OSS-CH-12",
            severity=Severity.MAY,
            status=Status.PASS if funding else Status.FAIL,
            domain=DOMAIN,
            summary=f"FUNDING at {funding}" if funding else "FUNDING.yml not present (optional)",
            auto_apply_safe=False,
        )
    )

    return out
