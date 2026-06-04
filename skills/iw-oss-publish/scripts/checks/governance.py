"""OSS-GOV — Governance documents."""

from __future__ import annotations

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "governance"


@register(id_prefix="OSS-GOV", order=16, domain=DOMAIN)
def governance(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    # Maintainer count — best effort from CODEOWNERS
    codeowners = ctx.exists("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")
    maintainer_refs: set[str] = set()
    if codeowners:
        body = ctx.read_text(codeowners) or ""
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for tok in stripped.split()[1:]:  # skip the pattern, collect owner handles
                if tok.startswith("@"):
                    maintainer_refs.add(tok)

    # Foundation-stewardship flag (config)
    foundation = ctx.config.get("governance", {}).get("foundation_stewardship", False)
    escalate = len(maintainer_refs) >= 4 or foundation

    gov = ctx.exists("GOVERNANCE.md", "docs/GOVERNANCE.md")
    if gov:
        out.append(
            Finding(
                id="OSS-GOV-01",
                severity=Severity.SHOULD,
                status=Status.PASS,
                domain=DOMAIN,
                summary=f"GOVERNANCE.md at {gov}",
                auto_apply_safe=False,
            )
        )
    elif escalate:
        out.append(
            Finding(
                id="OSS-GOV-01",
                severity=Severity.SHOULD,
                status=Status.FAIL,
                domain=DOMAIN,
                summary=f"GOVERNANCE.md missing ({'foundation track' if foundation else f'{len(maintainer_refs)} maintainer refs'})",
                remediation="Add GOVERNANCE.md documenting decision-making, merge authority, CoC chain.",
                auto_fix_available=False,
                auto_apply_safe=False,
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-GOV-01",
                severity=Severity.MAY,
                status=Status.FAIL,
                domain=DOMAIN,
                summary="GOVERNANCE.md not present (not required at this maintainer count)",
                auto_apply_safe=False,
            )
        )

    # OSS-GOV-02: MAINTAINERS file
    maint = ctx.exists("MAINTAINERS", "MAINTAINERS.md", "docs/MAINTAINERS.md")
    out.append(
        Finding(
            id="OSS-GOV-02",
            severity=Severity.MAY,
            status=Status.PASS if maint else Status.FAIL,
            domain=DOMAIN,
            summary=f"MAINTAINERS at {maint}"
            if maint
            else "No MAINTAINERS file (optional; CODEOWNERS can suffice)",
            auto_apply_safe=False,
        )
    )

    return out
