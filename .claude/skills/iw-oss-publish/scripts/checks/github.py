"""OSS-GH — GitHub live-settings checks (via gh CLI)."""

from __future__ import annotations

import json
import subprocess

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "github"


@register(id_prefix="OSS-GH", order=15, domain=DOMAIN)
def github_live(ctx: Context) -> list[Finding]:
    out: list[Finding] = []

    if ctx.config.get("disable_gh_live_checks"):
        out.append(
            Finding(
                id="OSS-GH-ALL",
                severity=Severity.INFO,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="GitHub live checks disabled via config",
                auto_apply_safe=False,
            )
        )
        return out

    if not ctx.has_tool("gh"):
        out.append(
            Finding(
                id="OSS-GH-ALL",
                severity=Severity.INFO,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="gh CLI unavailable — GitHub live checks skipped",
                auto_apply_safe=False,
            )
        )
        return out

    if not ctx.repo.has_remote:
        out.append(
            Finding(
                id="OSS-GH-ALL",
                severity=Severity.INFO,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="No git remote — GitHub live checks skipped",
                auto_apply_safe=False,
            )
        )
        return out

    # Best-effort repo metadata
    repo_data = _gh_repo_view(ctx)
    if not repo_data:
        out.append(
            Finding(
                id="OSS-GH-ALL",
                severity=Severity.INFO,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="`gh repo view` failed (not authenticated, or repo not on GitHub)",
                auto_apply_safe=False,
            )
        )
        return out

    is_private = repo_data.get("isPrivate", True)

    # OSS-GH-08: description non-empty
    desc = (repo_data.get("description") or "").strip()
    out.append(
        Finding(
            id="OSS-GH-08",
            severity=Severity.SHOULD,
            status=Status.PASS if desc else Status.FAIL,
            domain=DOMAIN,
            summary=f'Description: "{desc[:80]}"' if desc else "Description empty",
            remediation='Set via `gh repo edit --description "..."` (emitted in publish playbook).'
            if not desc
            else None,
            auto_apply_safe=False,
        )
    )

    # OSS-GH-09: ≥3 topics
    topics = repo_data.get("repositoryTopics") or []
    # Normalize: gh API returns list of {"name": "topic"} or list of strings
    if topics and isinstance(topics[0], dict):
        topics = [t.get("name", "") for t in topics]
    out.append(
        Finding(
            id="OSS-GH-09",
            severity=Severity.SHOULD,
            status=Status.PASS if len(topics) >= 3 else Status.FAIL,
            domain=DOMAIN,
            summary=f"{len(topics)} topic(s): {', '.join(topics) or '(none)'}",
            auto_apply_safe=False,
        )
    )

    # OSS-GH-10: homepage URL
    homepage = (repo_data.get("homepageUrl") or "").strip()
    out.append(
        Finding(
            id="OSS-GH-10",
            severity=Severity.SHOULD,
            status=Status.PASS if homepage else Status.FAIL,
            domain=DOMAIN,
            summary=f"Homepage: {homepage}" if homepage else "Homepage URL not set",
            auto_apply_safe=False,
        )
    )

    # OSS-GH-11: squash-merge enabled
    squash = repo_data.get("squashMergeAllowed")
    out.append(
        Finding(
            id="OSS-GH-11",
            severity=Severity.SHOULD,
            status=Status.PASS if squash else Status.FAIL,
            domain=DOMAIN,
            summary="Squash-merge enabled" if squash else "Squash-merge disabled",
            auto_apply_safe=False,
        )
    )

    # OSS-GH-12: merge-commit disabled
    merge_commit = repo_data.get("mergeCommitAllowed")
    out.append(
        Finding(
            id="OSS-GH-12",
            severity=Severity.MAY,
            status=Status.PASS if merge_commit is False else Status.FAIL,
            domain=DOMAIN,
            summary="Merge-commit disabled"
            if merge_commit is False
            else "Merge-commit enabled (consider disabling for linear history)",
            auto_apply_safe=False,
        )
    )

    # OSS-GH-13: delete-branch-on-merge
    delete_on_merge = repo_data.get("deleteBranchOnMerge")
    out.append(
        Finding(
            id="OSS-GH-13",
            severity=Severity.SHOULD,
            status=Status.PASS if delete_on_merge else Status.FAIL,
            domain=DOMAIN,
            summary="Delete-branch-on-merge enabled"
            if delete_on_merge
            else "Delete-branch-on-merge disabled",
            auto_apply_safe=False,
        )
    )

    # OSS-GH-14: ≥1 release
    releases = _gh_release_list(ctx)
    out.append(
        Finding(
            id="OSS-GH-14",
            severity=Severity.SHOULD,
            status=Status.PASS if releases else Status.FAIL,
            domain=DOMAIN,
            summary=f"{len(releases)} GitHub Release(s) present"
            if releases
            else "No GitHub Releases yet",
            auto_apply_safe=False,
        )
    )

    # OSS-GH-01: branch protection on main (requires extra API call)
    prot = _gh_branch_protection(ctx, "main")
    if prot is None:
        out.append(
            Finding(
                id="OSS-GH-01",
                severity=Severity.MUST,
                status=Status.SKIP,
                domain=DOMAIN,
                summary="Could not read branch protection (not found, not admin, or private-repo repo setting)",
                osps_control="OSPS-AC-03.01",
                auto_apply_safe=False,
            )
        )
    else:
        blocks_direct = not prot.get("allow_force_pushes", {}).get("enabled", True) or bool(
            prot.get("required_pull_request_reviews")
        )
        out.append(
            Finding(
                id="OSS-GH-01",
                severity=Severity.MUST if not is_private else Severity.SHOULD,
                status=Status.PASS if blocks_direct else Status.FAIL,
                domain=DOMAIN,
                summary="main branch protection blocks direct pushes"
                if blocks_direct
                else "main branch protection does NOT block direct pushes",
                osps_control="OSPS-AC-03.01",
                auto_apply_safe=False,
            )
        )

        # OSS-GH-02: branch deletion protection
        allow_deletions = prot.get("allow_deletions", {}).get("enabled", False)
        out.append(
            Finding(
                id="OSS-GH-02",
                severity=Severity.MUST if not is_private else Severity.SHOULD,
                status=Status.PASS if not allow_deletions else Status.FAIL,
                domain=DOMAIN,
                summary="main branch deletion disabled"
                if not allow_deletions
                else "main branch deletion ENABLED",
                osps_control="OSPS-AC-03.02",
                auto_apply_safe=False,
            )
        )

    return out


def _gh_repo_view(ctx: Context) -> dict | None:
    fields = [
        "isPrivate",
        "visibility",
        "description",
        "homepageUrl",
        "repositoryTopics",
        "squashMergeAllowed",
        "mergeCommitAllowed",
        "rebaseMergeAllowed",
        "deleteBranchOnMerge",
    ]
    try:
        r = subprocess.run(
            ["gh", "repo", "view", "--json", ",".join(fields)],
            cwd=ctx.target,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if r.returncode != 0:
            return None
        return json.loads(r.stdout)
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return None


def _gh_release_list(ctx: Context) -> list[dict]:
    try:
        r = subprocess.run(
            ["gh", "release", "list", "--limit", "1", "--json", "tagName,isLatest"],
            cwd=ctx.target,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if r.returncode != 0:
            return []
        return json.loads(r.stdout or "[]")
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return []


def _gh_branch_protection(ctx: Context, branch: str) -> dict | None:
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{{owner}}/{{repo}}/branches/{branch}/protection"],
            cwd=ctx.target,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if r.returncode != 0:
            return None
        return json.loads(r.stdout)
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return None
