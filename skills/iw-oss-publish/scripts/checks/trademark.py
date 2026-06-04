"""OSS-TM — Trademark, brand, name-collision checks."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "trademark"

HTTP_TIMEOUT = 8


@register(id_prefix="OSS-TM", order=12, domain=DOMAIN)
def trademark(ctx: Context) -> list[Finding]:
    out: list[Finding] = []
    name = ctx.config.get("project_name", ctx.target.name)

    # OSS-TM-01: TRADEMARK.md present
    tm = ctx.exists("TRADEMARK.md", "TRADEMARKS.md", "docs/TRADEMARK.md")
    out.append(
        Finding(
            id="OSS-TM-01",
            severity=Severity.SHOULD,
            status=Status.PASS if tm else Status.FAIL,
            domain=DOMAIN,
            summary=f"TRADEMARK at {tm}" if tm else "TRADEMARK.md missing",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-TM-02..05: name-collision HTTP probes
    # The project name can contain characters that aren't valid in a URL path
    # segment (spaces, slashes, etc.). urllib.request rejects control characters
    # outright, so percent-encode before interpolating.
    name_q = urllib.parse.quote(name, safe="")
    out.append(_probe("OSS-TM-02", "PyPI", f"https://pypi.org/pypi/{name_q}/json", name))
    out.append(_probe("OSS-TM-03", "npm", f"https://registry.npmjs.org/{name_q}", name))
    out.append(_probe("OSS-TM-04", "crates.io", f"https://crates.io/api/v1/crates/{name_q}", name))
    out.append(_probe_github("OSS-TM-05", ctx, name))

    # OSS-TM-06: USPTO Trademark Search — manual
    uspto = ctx.config.get("trademark", {}).get("uspto_searched")
    out.append(
        Finding(
            id="OSS-TM-06",
            severity=Severity.SHOULD,
            status=Status.PASS if uspto else Status.HUMAN_REQUIRED,
            domain=DOMAIN,
            summary=f"USPTO Trademark Search recorded: {uspto}"
            if uspto
            else "USPTO Trademark Search not yet recorded",
            remediation=(
                "Manual search: https://tmsearch.uspto.gov/ — record outcome in "
                '`.iw/oss-publish.toml` under [trademark] uspta_searched = "YYYY-MM-DD"'
            )
            if not uspto
            else None,
            auto_apply_safe=False,
        )
    )

    # OSS-TM-07: WIPO Global Brand Database — manual
    wipo = ctx.config.get("trademark", {}).get("wipo_searched")
    out.append(
        Finding(
            id="OSS-TM-07",
            severity=Severity.SHOULD,
            status=Status.PASS if wipo else Status.HUMAN_REQUIRED,
            domain=DOMAIN,
            summary=f"WIPO Global Brand Database search recorded: {wipo}"
            if wipo
            else "WIPO search not yet recorded",
            remediation=(
                "Manual search: https://branddb.wipo.int/ — record in .iw/oss-publish.toml "
                'under [trademark] wipo_searched = "YYYY-MM-DD"'
            )
            if not wipo
            else None,
            auto_apply_safe=False,
        )
    )

    # OSS-TM-08: README trademark notice (fallback when TRADEMARK.md absent)
    if not tm:
        readme = ctx.exists("README.md", "README.rst", "README")
        has_notice = False
        if readme:
            body = ctx.read_text(readme) or ""
            has_notice = ("trademark" in body.lower()) or ("®" in body) or ("™" in body)
        out.append(
            Finding(
                id="OSS-TM-08",
                severity=Severity.SHOULD,
                status=Status.PASS if has_notice else Status.FAIL,
                domain=DOMAIN,
                summary="README mentions trademark notice"
                if has_notice
                else "No TRADEMARK.md and README lacks trademark notice",
                remediation="`make_oss` appends a Trademark section to a generated README."
                if not has_notice
                else None,
                auto_fix_available=True,
                auto_apply_safe=True,
            )
        )

    return out


def _probe(check_id: str, registry: str, url: str, name: str) -> Finding:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "iw-oss-publish/0.1"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return Finding(
            id=check_id,
            severity=Severity.SHOULD,
            status=Status.SKIP,
            domain=DOMAIN,
            summary=f"{registry} name-collision probe failed (offline?)",
            auto_apply_safe=False,
        )

    if code == 404:
        return Finding(
            id=check_id,
            severity=Severity.SHOULD,
            status=Status.PASS,
            domain=DOMAIN,
            summary=f"Name `{name}` available on {registry}",
            auto_apply_safe=False,
        )
    if 200 <= code < 300:
        return Finding(
            id=check_id,
            severity=Severity.SHOULD,
            status=Status.HUMAN_REQUIRED,
            domain=DOMAIN,
            summary=f"Name `{name}` already taken on {registry}",
            remediation=f"Consider a scoped name (e.g., @innovation-ways/{name}) or rename.",
            auto_apply_safe=False,
        )
    return Finding(
        id=check_id,
        severity=Severity.SHOULD,
        status=Status.SKIP,
        domain=DOMAIN,
        summary=f"{registry} probe returned HTTP {code}",
        auto_apply_safe=False,
    )


def _probe_github(check_id: str, ctx: Context, name: str) -> Finding:
    own_org = ctx.config.get("company_github_org", "innovation-ways")
    # Skip if gh is unavailable
    if not ctx.has_tool("gh"):
        return Finding(
            id=check_id,
            severity=Severity.SHOULD,
            status=Status.SKIP,
            domain=DOMAIN,
            summary="gh CLI unavailable — GitHub name probe skipped",
            auto_apply_safe=False,
        )
    import subprocess

    try:
        r = subprocess.run(
            ["gh", "search", "repos", name, "--limit", "5", "--json", "fullName,stargazerCount"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if r.returncode != 0:
            return Finding(
                id=check_id,
                severity=Severity.SHOULD,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="gh search failed (not authenticated?)",
                auto_apply_safe=False,
            )
        data = json.loads(r.stdout or "[]")
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return Finding(
            id=check_id,
            severity=Severity.SHOULD,
            status=Status.SKIP,
            domain=DOMAIN,
            summary="gh search errored",
            auto_apply_safe=False,
        )

    # Filter out our own org
    others = [r for r in data if not str(r.get("fullName", "")).startswith(own_org + "/")]
    if not others:
        return Finding(
            id=check_id,
            severity=Severity.SHOULD,
            status=Status.PASS,
            domain=DOMAIN,
            summary=f"No GitHub name collisions outside {own_org}",
            auto_apply_safe=False,
        )
    top = others[0]
    return Finding(
        id=check_id,
        severity=Severity.SHOULD,
        status=Status.HUMAN_REQUIRED,
        domain=DOMAIN,
        summary=f"Existing GitHub repo: {top.get('fullName')} ({top.get('stargazerCount', 0)}★)",
        detail="Other matches: " + ", ".join(r.get("fullName", "?") for r in others[:5]),
        remediation="Review — the existing repo may or may not be a problem depending on stars/activity.",
        auto_apply_safe=False,
    )
