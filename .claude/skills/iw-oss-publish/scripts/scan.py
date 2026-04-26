#!/usr/bin/env python3
"""iw-oss-publish scan — run compliance checks against a target repository.

Usage:
    python3 scan.py [--target PATH] [--mode scan|make_oss|publish] [--verbose]

Exit codes:
    0   Clean (no MUST failures)
    1   Compliance failure (MUST finding unresolved)
    2   Setup / environment error
    130 User cancelled (Ctrl-C)

Writes artifacts to {target}/.iw/:
    oss-publish-findings.json
    oss-publish-report.md
    iw-oss-publish.sarif           (if any structural findings to report)
    gitleaks-tree.sarif            (gitleaks output, if tool available)
    gitleaks-history.sarif
    sbom.spdx.json                 (syft output, if tool available)
    sbom.cyclonedx.json
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

SKILL_VERSION = "0.1.0"

# Make `lib` and `checks` importable when scan.py is invoked directly.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import checks  # noqa: E402,F401  — side effect: registers all checks
from lib.config import load_config  # noqa: E402
from lib.context import Context, detect_ecosystems, detect_repo_info  # noqa: E402
from lib.registry import run_all  # noqa: E402
from lib.report import (  # noqa: E402
    compute_exit_code,
    emit_json,
    emit_markdown,
    emit_sarif_combined,
)
from lib.tools import detect_tools, missing_tier1  # noqa: E402

logger = logging.getLogger("iw-oss-publish")


def build_context(target: Path, mode: str) -> Context:
    """Construct the Context object for a scan."""
    target = target.resolve()
    if not (target / ".git").exists() and not (target / ".git").is_dir():
        # Could also be a detached git repo (e.g., worktree) — try rev-parse
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=target,
                check=True,
                capture_output=True,
                timeout=5,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            print(f"error: {target} is not a git repository", file=sys.stderr)
            sys.exit(2)

    iw_dir = target / ".iw"
    iw_dir.mkdir(parents=True, exist_ok=True)
    # Note: .iw/ in .gitignore is handled by OSS-ENV-04 check + make_oss fix,
    # not as a build_context side effect (which would dirty the working tree).

    cfg = load_config(target)
    tool_overrides = cfg.get("tools", {}).get("override", {}) or {}
    tools = detect_tools(overrides=tool_overrides)
    repo = detect_repo_info(target)
    ecosystems = detect_ecosystems(target)

    return Context(
        target=target,
        iw_dir=iw_dir,
        config=cfg,
        tools=tools,
        repo=repo,
        ecosystems=ecosystems,
        mode=mode,
    )


def _ensure_gitignore_entry(target: Path, entry: str) -> None:
    gi = target / ".gitignore"
    if not gi.exists():
        gi.write_text(entry + "\n", encoding="utf-8")
        return
    content = gi.read_text(encoding="utf-8", errors="replace")
    if entry in content.splitlines():
        return
    # Append, preserving trailing newline behavior
    sep = "" if content.endswith("\n") or content == "" else "\n"
    gi.write_text(content + sep + entry + "\n", encoding="utf-8")


def _print_missing_tools(tools: dict[str, str | None]) -> None:
    missing = missing_tier1(tools)
    if not missing:
        return
    print("", file=sys.stderr)
    print("⚠  Missing Tier-1 tools:", file=sys.stderr)
    for t in missing:
        print(f"   - {t}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Install with:", file=sys.stderr)
    print("  bash .claude/skills/iw-oss-publish/scripts/install_tools.sh", file=sys.stderr)
    print("", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="iw-oss-publish scan", description=__doc__)
    p.add_argument(
        "--target", "-t", type=Path, default=Path(), help="Target repository (default: cwd)"
    )
    p.add_argument(
        "--mode",
        choices=["scan"],
        default="scan",
        help="Mode of operation (only 'scan' is supported in Phase A)",
    )
    p.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    p.add_argument(
        "--no-tool-check",
        action="store_true",
        help="Do not abort on missing Tier-1 tools (useful for partial scans)",
    )
    return p.parse_args()


def _validate_mode(mode: str) -> None:
    if mode != "scan":
        print(f"error: unsupported mode '{mode}' — only 'scan' is supported in Phase A", file=sys.stderr)
        sys.exit(2)


def run_scan(ctx) -> int:
    """Shared scan body — used both by scan mode and as a subroutine of make_oss."""
    findings = run_all(ctx)
    emit_json(ctx, findings, skill_version=SKILL_VERSION)
    md_path = emit_markdown(ctx, findings)
    sarif_path = emit_sarif_combined(ctx, findings)
    return compute_exit_code(findings), findings, md_path, sarif_path


def run_make_oss(ctx, args) -> int:
    """Prepare a private repo for OSS release on a dedicated branch.

    Applies all auto-fixable recipes, emits a punchlist of human-judgment items,
    stages changes (does not commit).
    """
    import datetime

    from lib.fixes import apply_fix, available_fixes
    from lib.render import Renderer, build_render_context

    # ------------------------------------------------------------------
    # Preconditions
    # ------------------------------------------------------------------
    if ctx.repo.visibility == "public" and not args.force:
        print("error: repo is already public. Run with --force to override.", file=sys.stderr)
        return 2

    if not args.no_clean_check:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ctx.target,
            capture_output=True,
            text=True,
            check=False,
        )
        if status.stdout.strip():
            print(
                "error: working tree is not clean. Commit/stash first, or pass --no-clean-check.",
                file=sys.stderr,
            )
            print(status.stdout, file=sys.stderr)
            return 2

    # ------------------------------------------------------------------
    # Branch setup
    # ------------------------------------------------------------------
    today = datetime.date.today().strftime("%Y-%m-%d")
    prep_branch = f"iw-oss-publish/prep-{today}"
    current_branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=ctx.target,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()

    if current_branch != prep_branch:
        # Create or switch to prep branch
        existing = (
            subprocess.run(
                ["git", "rev-parse", "--verify", prep_branch],
                cwd=ctx.target,
                capture_output=True,
                text=True,
                check=False,
            ).returncode
            == 0
        )
        checkout_args = (
            ["git", "checkout", prep_branch] if existing else ["git", "checkout", "-b", prep_branch]
        )
        r = subprocess.run(
            checkout_args, cwd=ctx.target, capture_output=True, text=True, check=False
        )
        if r.returncode != 0:
            print(f"error: could not checkout {prep_branch}: {r.stderr.strip()}", file=sys.stderr)
            return 2
        logger.info("switched to %s", prep_branch)

    # ------------------------------------------------------------------
    # Baseline scan
    # ------------------------------------------------------------------
    logger.info("running baseline scan…")
    baseline_exit, baseline_findings, _, _ = run_scan(ctx)

    # ------------------------------------------------------------------
    # Apply fixes
    # ------------------------------------------------------------------
    renderer = Renderer()
    render_ctx = build_render_context(ctx.config, ctx.ecosystems)

    applicable: list[str] = []
    seen: set[str] = set()
    for f in baseline_findings:
        if (
            f.status.value in ("fail", "human_required")
            and f.auto_fix_available
            and f.id not in seen
        ):
            applicable.append(f.id)
            seen.add(f.id)

    # Also apply "always-try" fixes that aren't tied to a single finding:
    always_try = ["OSS-ENV-03", "OSS-ENV-04", "OSS-SEC-04", "PRE-COMMIT-CONFIG"]
    for fid in always_try:
        if fid not in seen:
            applicable.append(fid)
            seen.add(fid)

    applied_results = []
    for check_id in applicable:
        if check_id not in available_fixes():
            continue
        result = apply_fix(check_id, ctx, renderer, render_ctx)
        if result is None:
            continue
        applied_results.append(result)
        icon = {"applied": "✓", "skipped": "·", "error": "✗"}[result.status]
        print(f"  {icon} {check_id}: {result.summary}")

    # ------------------------------------------------------------------
    # Re-scan
    # ------------------------------------------------------------------
    logger.info("re-running scan after fixes…")
    # Rebuild context so the newly-written .iw/oss-publish.toml is picked up.
    fresh_ctx = build_context(args.target, args.mode)
    post_exit, post_findings, md_path, sarif_path = run_scan(fresh_ctx)

    # ------------------------------------------------------------------
    # Punchlist
    # ------------------------------------------------------------------
    punchlist_path = emit_punchlist(fresh_ctx, post_findings, applied_results, prep_branch)
    print("")
    print(f"→ compliance report: {md_path}")
    print(f"→ punchlist:         {punchlist_path}")

    # ------------------------------------------------------------------
    # Stage changes (do NOT commit — per make_oss contract)
    # ------------------------------------------------------------------
    subprocess.run(["git", "add", "-A"], cwd=ctx.target, check=False)
    n_staged_diff = subprocess.run(
        ["git", "diff", "--cached", "--numstat"],
        cwd=ctx.target,
        capture_output=True,
        text=True,
        check=False,
    )
    staged_count = len([l for l in n_staged_diff.stdout.splitlines() if l.strip()])
    print("")
    print(f"Staged {staged_count} file(s) on {prep_branch}. Review with:")
    print("  git diff --cached")
    print("")
    print("Then commit:")
    print("  git commit -s -m 'chore: prepare for public OSS release'")
    print("")

    return post_exit


def emit_punchlist(ctx, findings, applied, branch_name):
    """Write compliance-punchlist.md for make_oss mode."""
    from lib.types import Severity, Status

    lines = [
        f"# Compliance Punchlist — {ctx.config.get('project_name', '(unnamed)')}",
        "",
        f"Generated by `iw-oss-publish make_oss` on {ctx.repo.head_sha[:12] or 'unknown'}",
        f"Branch: `{branch_name}`",
        "",
        "Address the items below, then re-run `iw-oss-publish scan` to verify, ",
        "and finally `iw-oss-publish publish` to flip the repo to public.",
        "",
        "---",
        "",
        "## Applied Automatically",
        "",
    ]
    for r in applied:
        if r.status == "applied":
            lines.append(f"- ✅ **{r.check_id}** — {r.summary}")
            for f in r.files_written:
                lines.append(f"  - wrote `{f}`")
            for f in r.files_modified:
                lines.append(f"  - modified `{f}`")
    lines.append("")

    blockers = [
        f
        for f in findings
        if f.severity == Severity.MUST and f.status in (Status.FAIL, Status.HUMAN_REQUIRED)
    ]
    warnings = [
        f
        for f in findings
        if f.severity == Severity.SHOULD and f.status in (Status.FAIL, Status.HUMAN_REQUIRED)
    ]
    if blockers:
        lines.append("## MUST — still blocking")
        lines.append("")
        for f in blockers:
            lines.append(f"- [ ] **{f.id}** — {f.summary}")
            if f.remediation:
                lines.append(f"  - {f.remediation}")
        lines.append("")
    if warnings:
        lines.append("## SHOULD — recommended")
        lines.append("")
        for f in warnings:
            lines.append(f"- [ ] **{f.id}** — {f.summary}")
            if f.remediation:
                lines.append(f"  - {f.remediation}")
        lines.append("")

    out = ctx.iw_dir / "compliance-punchlist.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def run_publish(ctx, args) -> int:
    """Emit publish-playbook scripts + checklist for flipping the repo public.

    Never executes destructive git operations or `gh repo edit --visibility public`.
    The user runs the generated shell scripts manually.
    """
    from lib.publish import (
        suggest_history_strategy,
        write_filter_repo_script,
        write_gh_playbook,
        write_nuke_script,
        write_publish_checklist,
    )
    from lib.types import Severity, Status

    # ------------------------------------------------------------------
    # Preconditions
    # ------------------------------------------------------------------
    if ctx.repo.visibility == "public" and not args.force:
        print(
            "error: repo is already public. Use `scan` mode for ongoing compliance, "
            "or run with --force to regenerate the playbook.",
            file=sys.stderr,
        )
        return 2

    # ------------------------------------------------------------------
    # Pre-publish scan
    # ------------------------------------------------------------------
    logger.info("running pre-publish scan…")
    exit_code, findings, md_path, _ = run_scan(ctx)

    blockers = [
        f
        for f in findings
        if f.severity == Severity.MUST and f.status in (Status.FAIL, Status.HUMAN_REQUIRED)
    ]

    # ------------------------------------------------------------------
    # Extract signals for the history-strategy suggestion
    # ------------------------------------------------------------------
    history_secrets = 0
    non_noreply_emails = 0
    large_blobs = 0
    for f in findings:
        if f.id == "OSS-SEC-02" and f.status == Status.FAIL:
            history_secrets = f.evidence.get("finding_count", 0) or 0
        if f.id == "OSS-HIST-03" and f.status == Status.HUMAN_REQUIRED:
            non_noreply_emails = len(f.evidence.get("non_noreply_emails", []))
        if f.id == "OSS-HYG-04" and f.status == Status.FAIL:
            large_blobs = len(f.evidence.get("large_objects", []))

    pre_existing = ctx.config.get("history", {}).get("strategy")
    strategy = suggest_history_strategy(
        history_secrets, non_noreply_emails, large_blobs, pre_existing
    )

    # ------------------------------------------------------------------
    # Emit artifacts
    # ------------------------------------------------------------------
    nuke_path = write_nuke_script(ctx, history_secrets, 0)
    filter_path = write_filter_repo_script(ctx)
    playbook_path = write_gh_playbook(ctx, has_history_rewrite=(history_secrets > 0))
    checklist_path = write_publish_checklist(
        ctx,
        blockers=blockers,
        history_strategy_suggested=strategy,
        history_secrets=history_secrets,
        artifacts={
            "compliance report": md_path,
            "nuke-and-reinit script": nuke_path,
            "filter-repo surgical script": filter_path,
            "gh flip-to-public playbook": playbook_path,
        },
    )

    # ------------------------------------------------------------------
    # Hard-block if MUST findings remain
    # ------------------------------------------------------------------
    if blockers and not args.force:
        print("")
        print(f"✗ Pre-publish scan has {len(blockers)} MUST finding(s) unresolved.")
        for f in blockers[:5]:
            print(f"    - {f.id}: {f.summary}")
        if len(blockers) > 5:
            print(f"    … and {len(blockers) - 5} more (see checklist)")
        print("")
        print(f"Full list: {checklist_path}")
        print("")
        print("Run `iw-oss-publish make_oss` first, then re-run `publish`.")
        return 1

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("")
    print(f"→ publish checklist:  {checklist_path}")
    print(f"→ compliance report:  {md_path}")
    print(f"→ nuke script:        {nuke_path}")
    print(f"→ filter-repo script: {filter_path}")
    print(f"→ gh playbook:        {playbook_path}")
    print("")
    print(f"Suggested history strategy: {strategy.upper()}")
    if history_secrets > 0:
        print(f"⚠  {history_secrets} secret(s) in history — PRESERVE is NOT an option.")
    print("")
    print("Next: review the checklist, run the chosen history-rewrite script,")
    print("then run `bash .iw/publish-playbook.sh` to flip public.")

    return 0


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    _validate_mode(args.mode)

    ctx = build_context(args.target, args.mode)
    _print_missing_tools(ctx.tools)

    logger.info("scanning %s (mode=%s)", ctx.target, ctx.mode)
    exit_code, _, md_path, sarif_path = run_scan(ctx)
    print(md_path.read_text(encoding="utf-8"))
    print("")
    print(f"→ findings JSON: {ctx.iw_dir / 'oss-publish-findings.json'}")
    print(f"→ report:        {md_path}")
    if sarif_path:
        print(f"→ SARIF:         {sarif_path}")
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\naborted", file=sys.stderr)
        sys.exit(130)
