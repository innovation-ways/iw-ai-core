"""OSS-REL — Release provenance: CHANGELOG, conventional commits, release automation."""

from __future__ import annotations

import re
import subprocess

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "release"

CONV_COMMIT_RE = re.compile(
    r"^(feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert)(\([^)]+\))?!?:"
)


@register(id_prefix="OSS-REL", order=14, domain=DOMAIN)
def release(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    # OSS-REL-01: CHANGELOG.md
    chlog = ctx.exists("CHANGELOG.md", "CHANGELOG", "HISTORY.md", "NEWS.md")
    out.append(
        Finding(
            id="OSS-REL-01",
            severity=Severity.SHOULD,
            status=Status.PASS if chlog else Status.FAIL,
            domain=DOMAIN,
            summary=f"CHANGELOG at {chlog}" if chlog else "CHANGELOG missing",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-REL-02: conventional commits in recent history
    recent_subjects = _recent_commit_subjects(ctx.target, count=20)
    if not recent_subjects:
        out.append(
            Finding(
                id="OSS-REL-02",
                severity=Severity.SHOULD,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="No recent commits to analyze",
                auto_apply_safe=False,
            )
        )
    else:
        conv = sum(1 for s in recent_subjects if CONV_COMMIT_RE.match(s.strip()))
        ratio = conv / len(recent_subjects)
        threshold = 0.7
        out.append(
            Finding(
                id="OSS-REL-02",
                severity=Severity.SHOULD,
                status=Status.PASS if ratio >= threshold else Status.FAIL,
                domain=DOMAIN,
                summary=f"Conventional Commits: {conv}/{len(recent_subjects)} ({int(ratio * 100)}%)",
                remediation=f"Aim for ≥{int(threshold * 100)}% conventional commits for release automation."
                if ratio < threshold
                else None,
                auto_apply_safe=False,
            )
        )

    # OSS-REL-03: release-please workflow present.
    # Accept the un-pinned `@v4` form OR the SHA-pinned form with `# v4` (or
    # `# v4.x.y`) on the same line — SHA-pinning is mandated by OSS-CI-02,
    # so requiring the bare `@v4` would put the two checks in direct conflict.
    import re as _re_rel

    rp = ctx.path(".github/workflows/release-please.yml")
    rp_text = rp.read_text(encoding="utf-8", errors="replace") if rp.exists() else ""
    _v4_unpinned = "googleapis/release-please-action@v4" in rp_text
    _v4_sha_pinned = bool(
        _re_rel.search(
            r"googleapis/release-please-action@[0-9a-f]{7,40}\s*#\s*v4(?:\.\d+)*\b",
            rp_text,
        )
    )
    has_v4 = _v4_unpinned or _v4_sha_pinned
    if rp.exists() and has_v4:
        out.append(
            Finding(
                id="OSS-REL-03",
                severity=Severity.SHOULD,
                status=Status.PASS,
                domain=DOMAIN,
                summary="release-please v4 workflow present",
                auto_apply_safe=False,
            )
        )
    elif rp.exists():
        out.append(
            Finding(
                id="OSS-REL-03",
                severity=Severity.SHOULD,
                status=Status.FAIL,
                domain=DOMAIN,
                summary="release-please.yml present but not referencing googleapis/release-please-action@v4",
                remediation="Update to `googleapis/release-please-action@v4` (archived google-github-actions fork must not be used).",
                auto_fix_available=True,
                auto_apply_safe=False,
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-REL-03",
                severity=Severity.SHOULD,
                status=Status.FAIL,
                domain=DOMAIN,
                summary="release-please.yml missing",
                remediation="`make_oss` renders release-please.yml from template.",
                auto_fix_available=True,
                auto_apply_safe=True,
            )
        )

    # OSS-REL-04: build-provenance attestation referenced in a release workflow
    wf_dir = ctx.target / ".github" / "workflows"
    has_attest = False
    if wf_dir.exists():
        for wf in wf_dir.glob("*.yml"):
            body = wf.read_text(encoding="utf-8", errors="replace")
            if "actions/attest-build-provenance" in body:
                has_attest = True
                break
    out.append(
        Finding(
            id="OSS-REL-04",
            severity=Severity.SHOULD,
            status=Status.PASS if has_attest else Status.FAIL,
            domain=DOMAIN,
            summary="actions/attest-build-provenance referenced"
            if has_attest
            else "No workflow references actions/attest-build-provenance",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-REL-05: semver tag exists
    tags = _list_tags(ctx.target)
    semver = [t for t in tags if re.match(r"^v?\d+\.\d+\.\d+", t)]
    if semver:
        out.append(
            Finding(
                id="OSS-REL-05",
                severity=Severity.SHOULD,
                status=Status.PASS,
                domain=DOMAIN,
                summary=f"{len(semver)} semver tag(s) present (latest: {semver[-1]})",
                auto_apply_safe=False,
            )
        )
    else:
        out.append(
            Finding(
                id="OSS-REL-05",
                severity=Severity.SHOULD,
                status=Status.FAIL,
                domain=DOMAIN,
                summary="No semver tags in the repository",
                remediation="Tag a release: `git tag -s v0.1.0 -m 'Initial release'`",
                auto_apply_safe=False,
            )
        )

    return out


def _recent_commit_subjects(target, count: int) -> list[str]:
    try:
        r = subprocess.run(
            ["git", "log", f"-{count}", "--format=%s"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return [s for s in r.stdout.splitlines() if s]
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def _list_tags(target) -> list[str]:
    try:
        r = subprocess.run(
            ["git", "tag", "-l", "--sort=creatordate"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return [t for t in r.stdout.splitlines() if t]
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
