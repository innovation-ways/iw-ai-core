"""OSS-HIST — Git history checks."""

from __future__ import annotations

import subprocess

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "history"


@register(id_prefix="OSS-HIST", order=4, domain=DOMAIN)
def history(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    # OSS-HIST-01: strategy chosen (publish mode only — INFO in scan)
    strategy = ctx.config.get("history", {}).get("strategy")
    sev = Severity.MUST if ctx.mode == "publish" else Severity.INFO
    if strategy:
        out.append(
            Finding(
                id="OSS-HIST-01",
                severity=Severity.INFO,
                status=Status.PASS,
                domain=DOMAIN,
                summary=f"History strategy recorded: {strategy}",
                auto_apply_safe=False,
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-HIST-01",
                severity=sev,
                status=Status.HUMAN_REQUIRED if ctx.mode == "publish" else Status.SKIP,
                domain=DOMAIN,
                summary="History strategy not yet chosen",
                remediation="`publish` mode will ask and record this decision."
                if ctx.mode == "publish"
                else "Will be asked during `publish`.",
                auto_apply_safe=False,
            )
        )

    # OSS-HIST-03: non-noreply author emails
    emails = _enumerate_author_emails(ctx.target)
    non_noreply = sorted(e for e in emails if not e.endswith("@users.noreply.github.com"))
    if not emails:
        out.append(
            Finding(
                id="OSS-HIST-03",
                severity=Severity.SHOULD,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="Unable to enumerate author emails (empty history?)",
                auto_apply_safe=False,
            )
        )
    elif not non_noreply:
        out.append(
            Finding(
                id="OSS-HIST-03",
                severity=Severity.SHOULD,
                status=Status.PASS,
                domain=DOMAIN,
                summary=f"All {len(emails)} contributor email(s) use GitHub noreply",
                auto_apply_safe=False,
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-HIST-03",
                severity=Severity.SHOULD,
                status=Status.HUMAN_REQUIRED,
                domain=DOMAIN,
                summary=f"{len(non_noreply)} non-noreply contributor email(s) in history",
                detail=", ".join(non_noreply[:10]) + (" …" if len(non_noreply) > 10 else ""),
                remediation=(
                    "Decide whether to accept, contact contributors, or rewrite history "
                    "(see history_rewrite.md). For future commits, configure "
                    "`git config user.email ID+username@users.noreply.github.com`."
                ),
                evidence={"non_noreply_emails": non_noreply},
                auto_apply_safe=False,
            )
        )

    # OSS-HIST-04: submodules pointing to internal URLs
    internal_suffixes = ctx.config.get("internal_fqdn_suffixes", [])
    internal_email_domains = ctx.config.get("internal_email_domains", [])
    submodules = _enumerate_submodule_urls(ctx.target)
    flagged = [
        s
        for s in submodules
        if any(suf in s for suf in internal_suffixes) or any(d in s for d in internal_email_domains)
    ]
    out.append(
        Finding(
            id="OSS-HIST-04",
            severity=Severity.MUST if ctx.mode == "publish" else Severity.SHOULD,
            status=Status.PASS if not flagged else Status.FAIL,
            domain=DOMAIN,
            summary="No submodules point to internal URLs"
            if not flagged
            else f"{len(flagged)} submodule(s) reference internal URLs",
            detail=", ".join(flagged)
            if flagged
            else (f"{len(submodules)} submodule(s) inspected." if submodules else "No submodules."),
            remediation="Remove internal submodules or redirect to public mirrors before publish."
            if flagged
            else None,
            auto_apply_safe=False,
        )
    )

    return out


def _enumerate_author_emails(target) -> set[str]:
    try:
        r = subprocess.run(
            ["git", "log", "--all", "--format=%ae"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return {line.strip() for line in r.stdout.splitlines() if line.strip()}
    except (subprocess.SubprocessError, FileNotFoundError):
        return set()


def _enumerate_submodule_urls(target) -> list[str]:
    gm = target / ".gitmodules"
    if not gm.exists():
        return []
    urls: list[str] = []
    for line in gm.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("url"):
            _, _, value = line.partition("=")
            urls.append(value.strip())
    return urls
