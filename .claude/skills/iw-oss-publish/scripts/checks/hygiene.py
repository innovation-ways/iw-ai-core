"""OSS-HYG — Repository hygiene."""

from __future__ import annotations

import fnmatch
import subprocess

from lib.context import Context
from lib.registry import register
from lib.types import Finding, Severity, Status

DOMAIN = "hygiene"

SECRET_PATTERNS_IN_GITIGNORE = [".env", "*.pem", "*.key", "*.pfx", "*.p12"]
LANGUAGE_IGNORES = {
    "python": ["__pycache__/", ".venv/", "*.pyc", ".pytest_cache/"],
    "node": ["node_modules/"],
    "go": [],  # go doesn't require ignores for common dev
    "rust": ["target/"],
    "java": ["target/", "build/"],
}

SENSITIVE_GLOBS = [
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    "*.tfstate",
    "*.tfstate.backup",
    "terraform.tfvars",
]

# Basenames that are literal `.env` or common per-environment variants.
SENSITIVE_ENV_BASENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    ".env.test",
}

# Common template basenames that are safe to commit.
SAFE_ENV_BASENAMES = {
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.dist",
    ".env.defaults",
    "env.example",
    "env.sample",
}


@register(id_prefix="OSS-HYG", order=2, domain=DOMAIN)
def hygiene(ctx: Context) -> list[Finding]:
    out: list[Finding] = []
    gitignore = ctx.target / ".gitignore"
    gi_lines = (
        gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
        if gitignore.exists()
        else []
    )
    gi_set = {
        line.strip() for line in gi_lines if line.strip() and not line.strip().startswith("#")
    }

    # OSS-HYG-01: .gitignore excludes secret patterns
    missing = [p for p in SECRET_PATTERNS_IN_GITIGNORE if p not in gi_set]
    out.append(
        Finding(
            id="OSS-HYG-01",
            severity=Severity.MUST,
            status=Status.PASS if not missing else Status.FAIL,
            domain=DOMAIN,
            summary=".gitignore covers secret/key patterns"
            if not missing
            else f".gitignore missing {len(missing)} secret pattern(s)",
            detail="Missing patterns: " + ", ".join(missing) if missing else "",
            remediation="`make_oss` will append the missing patterns." if missing else None,
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-HYG-02: no tracked sensitive files
    tracked = ctx.tracked_files()
    violations: list[str] = []
    for t in tracked:
        basename = t.rsplit("/", 1)[-1]
        if basename in SAFE_ENV_BASENAMES:
            continue  # explicit template allowlist
        if basename in SENSITIVE_ENV_BASENAMES:
            violations.append(t)
            continue
        if any(fnmatch.fnmatch(t, g) or fnmatch.fnmatch(basename, g) for g in SENSITIVE_GLOBS):
            violations.append(t)
    out.append(
        Finding(
            id="OSS-HYG-02",
            severity=Severity.MUST,
            status=Status.PASS if not violations else Status.FAIL,
            domain=DOMAIN,
            summary="No sensitive files tracked"
            if not violations
            else f"{len(violations)} sensitive file(s) tracked in git",
            detail="Tracked: " + ", ".join(violations[:20]) + (" …" if len(violations) > 20 else "")
            if violations
            else "",
            remediation="Remove from git history and add to .gitignore (see history_rewrite.md)."
            if violations
            else None,
            evidence={"violations": violations[:50]},
            auto_apply_safe=False,
        )
    )

    # OSS-HYG-03: language ignores
    lang_missing: list[str] = []
    for eco in ctx.ecosystems:
        for pat in LANGUAGE_IGNORES.get(eco, []):
            if pat not in gi_set:
                lang_missing.append(f"{eco}:{pat}")
    out.append(
        Finding(
            id="OSS-HYG-03",
            severity=Severity.SHOULD,
            status=Status.PASS if not lang_missing else Status.FAIL,
            domain=DOMAIN,
            summary=".gitignore covers detected ecosystems"
            if not lang_missing
            else f".gitignore missing language entries ({len(lang_missing)})",
            detail="Missing: " + ", ".join(lang_missing) if lang_missing else "",
            auto_fix_available=True,
            auto_apply_safe=True,
        )
    )

    # OSS-HYG-04: no blob >50 MB in history (git rev-list)
    large_objects = _find_large_objects(ctx.target, threshold_bytes=50 * 1024 * 1024)
    out.append(
        Finding(
            id="OSS-HYG-04",
            severity=Severity.SHOULD,
            status=Status.PASS if not large_objects else Status.FAIL,
            domain=DOMAIN,
            summary="No blobs >50MB in history"
            if not large_objects
            else f"{len(large_objects)} large blob(s) in history",
            detail="Largest: "
            + ", ".join(f"{p} ({s // 1024 // 1024}MB)" for s, p in large_objects[:5])
            if large_objects
            else "",
            remediation="Consider `git-filter-repo` or LFS migration; see history_rewrite.md."
            if large_objects
            else None,
            evidence={
                "large_objects": [{"size_bytes": s, "path": p} for s, p in large_objects[:20]]
            },
            auto_apply_safe=False,
        )
    )

    # OSS-HYG-05: no blob >10 MB in working tree (not in LFS)
    large_wt = _large_working_tree_files(ctx.target, tracked, threshold_bytes=10 * 1024 * 1024)
    out.append(
        Finding(
            id="OSS-HYG-05",
            severity=Severity.SHOULD,
            status=Status.PASS if not large_wt else Status.FAIL,
            domain=DOMAIN,
            summary="No large files in working tree"
            if not large_wt
            else f"{len(large_wt)} large file(s) in working tree (>10MB)",
            evidence={"paths": large_wt[:20]},
            auto_apply_safe=False,
        )
    )

    # OSS-HYG-06: default branch is main
    branch = ctx.repo.current_branch
    default_main = branch == "main" or branch == ""  # empty in detached HEAD, don't fail
    out.append(
        Finding(
            id="OSS-HYG-06",
            severity=Severity.MAY,
            status=Status.PASS if default_main else Status.FAIL,
            domain=DOMAIN,
            summary=f"Current branch: {branch or '(detached)'}",
            remediation="Rename to 'main' before public release (GitHub convention)."
            if not default_main
            else None,
            auto_apply_safe=False,
        )
    )

    return out


def _find_large_objects(target, threshold_bytes: int) -> list[tuple[int, str]]:
    try:
        # rev-list | cat-file to get blob sizes
        r = subprocess.run(
            ["git", "rev-list", "--objects", "--all"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if r.returncode != 0:
            return []
        candidates = r.stdout.splitlines()
        batch_check = subprocess.run(
            ["git", "cat-file", "--batch-check=%(objecttype) %(objectsize) %(objectname)"],
            cwd=target,
            input="\n".join(c.split(" ", 1)[0] for c in candidates if c),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        # Build path map: sha -> path (best-effort)
        path_by_sha: dict[str, str] = {}
        for c in candidates:
            parts = c.split(" ", 1)
            if len(parts) == 2:
                path_by_sha[parts[0]] = parts[1]
        results: list[tuple[int, str]] = []
        for line in batch_check.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "blob":
                try:
                    size = int(parts[1])
                except ValueError:
                    continue
                if size > threshold_bytes:
                    results.append((size, path_by_sha.get(parts[2], parts[2])))
        results.sort(reverse=True)
        return results
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def _large_working_tree_files(target, tracked: list[str], threshold_bytes: int) -> list[str]:
    large: list[str] = []
    for rel in tracked:
        p = target / rel
        try:
            if p.is_file() and p.stat().st_size > threshold_bytes:
                large.append(rel)
        except OSError:
            continue
    return large
