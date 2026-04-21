"""OSS-LIC — License file presence, SPDX match, copyright correctness."""

from __future__ import annotations

import datetime
import re

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "license"

LICENSE_CANDIDATES = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md"]
OSI_APPROVED = {
    "Apache-2.0",
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "0BSD",
    "MPL-2.0",
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "EPL-2.0",
    "CDDL-1.0",
    "Unlicense",
}


@register(id_prefix="OSS-LIC", order=8, domain=DOMAIN)
def license_checks(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    # OSS-LIC-01: LICENSE file present
    found = ctx.exists(*LICENSE_CANDIDATES)
    out.append(
        Finding(
            id="OSS-LIC-01",
            severity=Severity.MUST,
            status=Status.PASS if found else Status.FAIL,
            domain=DOMAIN,
            summary=f"LICENSE present at {found}" if found else "LICENSE file missing",
            osps_control="OSPS-LE-03.01",
            auto_fix_available=True,
            source_research=["R-00062 #7", "R-00062 #17"],
        )
    )

    license_text = ctx.read_text(found) if found else None
    declared = ctx.config.get("license", "Apache-2.0")

    # OSS-LIC-02: license is OSI-approved
    osi_ok = declared in OSI_APPROVED
    out.append(
        Finding(
            id="OSS-LIC-02",
            severity=Severity.MUST,
            status=Status.PASS if osi_ok else Status.FAIL,
            domain=DOMAIN,
            summary=f"Declared license '{declared}' is OSI-approved"
            if osi_ok
            else f"Declared license '{declared}' is not on OSI-approved list",
            osps_control="OSPS-LE-02.01",
        )
    )

    # OSS-LIC-03: SPDX identifier matches declared
    if found and license_text:
        match = _detect_spdx(license_text)
        if match is None:
            out.append(
                Finding(
                    id="OSS-LIC-03",
                    severity=Severity.MUST,
                    status=Status.HUMAN_REQUIRED,
                    domain=DOMAIN,
                    summary="Could not auto-detect SPDX ID from LICENSE text",
                    remediation="Verify LICENSE is a verbatim copy of the declared license.",
                )
            )
        elif match == declared:
            out.append(
                Finding(
                    id="OSS-LIC-03",
                    severity=Severity.MUST,
                    status=Status.PASS,
                    domain=DOMAIN,
                    summary=f"LICENSE matches declared SPDX '{declared}'",
                )
            )
        else:
            out.append(
                Finding(
                    id="OSS-LIC-03",
                    severity=Severity.MUST,
                    status=Status.FAIL,
                    domain=DOMAIN,
                    summary=f"LICENSE text matches '{match}' but config declares '{declared}'",
                    remediation="Reconcile: either change config.license or replace LICENSE text.",
                )
            )

    # OSS-LIC-04: copyright line has company_legal_name
    if found and license_text:
        legal_name = ctx.config.get("company_legal_name", "Innovation Ways - Unipessoal LDA")
        has_legal = legal_name in license_text
        out.append(
            Finding(
                id="OSS-LIC-04",
                severity=Severity.MUST,
                status=Status.PASS if has_legal else Status.HUMAN_REQUIRED,
                domain=DOMAIN,
                summary=f"Copyright line includes '{legal_name}'"
                if has_legal
                else f"Copyright line does not include '{legal_name}'",
                remediation="Review LICENSE — edit in place is not auto-applied."
                if not has_legal
                else None,
            )
        )

    # OSS-LIC-05: copyright year current
    if found and license_text:
        years = _extract_years(license_text)
        now = datetime.date.today().year
        ok = bool(years) and max(years) >= now - 1
        out.append(
            Finding(
                id="OSS-LIC-05",
                severity=Severity.SHOULD,
                status=Status.PASS if ok else Status.FAIL,
                domain=DOMAIN,
                summary=f"Copyright year range up-to-date (max={max(years)})"
                if ok
                else "Copyright year is stale or missing",
                remediation="`make_oss` will rewrite to include current year." if not ok else None,
                auto_fix_available=True,
            )
        )

    # OSS-LIC-06: NOTICE present for Apache-2.0
    if declared == "Apache-2.0":
        notice = ctx.exists("NOTICE", "NOTICE.md", "NOTICE.txt")
        out.append(
            Finding(
                id="OSS-LIC-06",
                severity=Severity.SHOULD,
                status=Status.PASS if notice else Status.FAIL,
                domain=DOMAIN,
                summary=f"NOTICE present at {notice}"
                if notice
                else "NOTICE file missing (Apache-2.0 projects should have one)",
                remediation="`make_oss` renders NOTICE from template." if not notice else None,
                auto_fix_available=True,
            )
        )

    return out


def _detect_spdx(text: str) -> str | None:
    """Heuristic SPDX detection from license body."""
    t = text.lower()
    if "apache license" in t and "version 2.0" in t:
        return "Apache-2.0"
    if "mit license" in t and "permission is hereby granted" in t:
        return "MIT"
    if "isc license" in t:
        return "ISC"
    if (
        "bsd 3-clause" in t
        or "redistribution and use in source and binary" in t
        and "endorse or promote" in t
    ):
        return "BSD-3-Clause"
    if "bsd 2-clause" in t:
        return "BSD-2-Clause"
    if "gnu general public license" in t and "version 3" in t:
        return "GPL-3.0-or-later"
    if "gnu affero general public license" in t:
        return "AGPL-3.0-or-later"
    if "zero-clause bsd" in t or "0bsd" in t:
        return "0BSD"
    if "unlicense" in t and "public domain" in t:
        return "Unlicense"
    return None


def _extract_years(text: str) -> list[int]:
    return [int(m.group()) for m in re.finditer(r"\b(19|20)\d{2}\b", text)]
