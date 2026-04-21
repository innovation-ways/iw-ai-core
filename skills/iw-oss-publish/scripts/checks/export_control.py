"""OSS-EXP — Export control (EAR / crypto classification)."""

from __future__ import annotations

import subprocess

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "export"

CRYPTO_IMPORTS = {
    "python": [
        r"\bimport\s+cryptography\b",
        r"\bfrom\s+cryptography\b",
        r"\bimport\s+nacl\b",
        r"\bfrom\s+nacl\b",
        r"\bimport\s+Crypto\b",
        r"\bimport\s+pycryptodome\b",
    ],
    "node": [
        r"require\(['\"]crypto['\"]\)",
        r"from\s+['\"]crypto['\"]",
        r"from\s+['\"]node-forge['\"]",
        r"from\s+['\"]sjcl['\"]",
        r"from\s+['\"]tweetnacl['\"]",
    ],
    "go": [r"\bcrypto/[a-z]+"],
    "rust": [r"\bring::", r"\brustls::", r"\baes::", r"\bchacha20::"],
}


@register(id_prefix="OSS-EXP", order=11, domain=DOMAIN)
def export_control(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    if not ctx.has_tool("ripgrep"):
        out.append(
            Finding(
                id="OSS-EXP-01",
                severity=Severity.SHOULD,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="ripgrep unavailable — crypto import scan skipped",
            )
        )
        return out

    patterns: list[str] = []
    for eco in ctx.ecosystems:
        patterns.extend(CRYPTO_IMPORTS.get(eco, []))

    if not patterns:
        out.append(
            Finding(
                id="OSS-EXP-01",
                severity=Severity.SHOULD,
                status=Status.PASS,
                domain=DOMAIN,
                summary="No ecosystems with crypto patterns detected",
            )
        )
        return out

    hits: list[str] = []
    for p in patterns:
        try:
            r = subprocess.run(
                [
                    "rg",
                    "--no-heading",
                    "--with-filename",
                    "--line-number",
                    "--color=never",
                    "-P",
                    p,
                    str(ctx.target),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            hits.extend(ln for ln in r.stdout.splitlines() if ln.strip())
        except (subprocess.SubprocessError, FileNotFoundError):
            continue

    already_attested = ctx.config.get("export_control", {}).get("standard_crypto_only")

    if not hits:
        out.append(
            Finding(
                id="OSS-EXP-01",
                severity=Severity.SHOULD,
                status=Status.PASS,
                domain=DOMAIN,
                summary="No crypto library imports detected",
                source_research=["R-00062 #10"],
            )
        )
    elif already_attested:
        out.append(
            Finding(
                id="OSS-EXP-01",
                severity=Severity.SHOULD,
                status=Status.PASS,
                domain=DOMAIN,
                summary=f"{len(hits)} crypto import(s); attested as standard-only",
                detail="`.iw/oss-publish.toml` export_control.standard_crypto_only = true",
                source_research=["R-00062 #10"],
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-EXP-01",
                severity=Severity.SHOULD,
                status=Status.HUMAN_REQUIRED,
                domain=DOMAIN,
                summary=f"{len(hits)} crypto import(s) detected — classify before publish",
                detail="Standard-library wrappers are typically exempt under EAR 2021 TSU rule. "
                "Custom or non-standard crypto may require BIS/NSA notification.\n\n"
                "Sample hits:\n" + "\n".join(hits[:10]),
                remediation=(
                    "Review each hit; if all are standard crypto via established libraries, "
                    "record `[export_control] standard_crypto_only = true` in .iw/oss-publish.toml. "
                    "If non-standard crypto is implemented, consult legal on BIS/NSA notification."
                ),
                evidence={"sample_hits": hits[:20]},
                source_research=["R-00062 #10"],
            )
        )

    # OSS-EXP-02: conditional MUST if non-standard crypto flagged
    if ctx.config.get("export_control", {}).get("non_standard_crypto_notified") is False:
        out.append(
            Finding(
                id="OSS-EXP-02",
                severity=Severity.MUST,
                status=Status.HUMAN_REQUIRED,
                domain=DOMAIN,
                summary="Non-standard crypto present; BIS/NSA notification flag set to false",
                remediation="Complete notification or change classification before publish.",
            )
        )

    return out
