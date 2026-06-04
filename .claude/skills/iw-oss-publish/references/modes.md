# Modes — Detailed Walkthroughs

This file expands on the modes defined in `SKILL.md`. It covers the exact sub-steps, decision points, and error-handling behavior for each mode.

---

## Shared Pre-flight (every mode)

Before any mode executes, the skill must:

1. **Validate target is a git repo**: `git -C {target} rev-parse --git-dir` (abort if fails).
2. **Detect visibility**: `gh repo view --json isPrivate,visibility 2>/dev/null` — record `private|public|unknown`. "unknown" when gh is not authenticated or the repo has no GitHub remote yet.
3. **Detect ecosystems present**: look for `pyproject.toml` / `setup.py` / `requirements*.txt` (Python), `package.json` (Node), `go.mod` (Go), `Cargo.toml` (Rust), `pom.xml` / `build.gradle*` (JVM).
4. **Load config**: per `SKILL.md` Step 2.
5. **Verify tool availability**: record which Tier-1 and Tier-2 tools are installed (`command -v {tool}`). Do not install — `install_tools.sh` is a separate explicit step.
6. **Ensure output dir**: `mkdir -p {target}/.iw`. Add `.iw/` to `.gitignore` if missing.

If any Tier-1 tool is missing, print the exact install command and abort the mode (no partial runs).

---

## `scan` Mode

### Purpose

Read-only audit. Answers "where does this repo stand against the OSS-release bar?" without touching working-tree or history.

### Algorithm

```
1. Pre-flight (shared).
2. Run check catalog in dependency order (see checks.md "Execution order").
3. Aggregate findings by severity: MUST / SHOULD / MAY.
4. Emit artifacts:
   - .iw/oss-publish-report.md     (markdown report)
   - .iw/oss-publish-findings.json (machine-readable)
   - .iw/gitleaks.sarif            (from the secrets check)
   - .iw/sbom.spdx.json            (from syft)
   - .iw/sbom.cyclonedx.json       (from syft)
5. Print the report body to console.
6. Exit 1 if any MUST finding unresolved, else 0.
```

### Exit contract

| Outcome | Exit code | Notes |
|---------|-----------|-------|
| No MUST unresolved, no SHOULD | 0 | Clean |
| No MUST unresolved, SHOULD present | 0 | Warning-level; scan succeeded |
| Any MUST unresolved | 1 | Blocker present; user must remediate |
| Tool missing / config invalid / git not found | 2 | Setup error, not a compliance finding |

### Idempotency

`scan` is pure and idempotent. Re-running overwrites `.iw/*` artifacts. No commits, no stash, no branch changes.

### Running on an already-public repo

`scan` works identically regardless of visibility. When `isPrivate=false`, some checks change their advisory text (e.g., secret-scanning: "enabled — verify push protection" vs "enable after flip"). Severity does not change.

---

## Per-finding Fix (Phase C)

### Purpose

Apply an auto-fixable check's remediation directly to the target repository.

### CLI

```bash
uv run iw oss fix <CHECK_ID> [--apply]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `CHECK_ID` | Yes | The check identifier (e.g., `OSS-LIC-01`, `OSS-CH-03`) |
| `--apply` | No | Without this flag, previews changes without writing |

### Algorithm

```
1. Pre-flight (shared).
2. Validate CHECK_ID exists in the check catalog.
3. Verify the check is marked auto-fixable (auto_fix != 'no').
4. If --apply not passed: print what would change and exit 0.
5. If --apply passed: apply the fix to the working tree.
6. Exit 0 on success, 1 if fix failed.
```

### What gets fixed

Per-check auto-fixes are documented in the check catalog. Fixes write to the working tree only — no commits, no branch switches.

### Idempotency

Re-running with `--apply` on an already-fixed check is safe — the fix detects existing correct state and is a no-op.

---

## Mode Selection Cheat Sheet

| User goal | Mode | Example |
|-----------|------|---------|
| "Show me what's blocking OSS release" | `scan` | `uv run iw oss scan` |
| "Check whether this public repo is still compliant" | `scan` | `uv run iw oss scan ~/work/my-public-oss` |
| "Fix a specific finding" | `fix` | `uv run iw oss fix OSS-LIC-01 --apply` |
| "I flipped public and want to ensure drift hasn't crept in" | `scan` | `uv run iw oss scan` |

---

## Error-Handling Summary

| Situation | Behavior |
|-----------|----------|
| Target not a git repo | Abort, exit 2 |
| Tier-1 tool missing | Abort with install command, exit 2 |
| Config file malformed | Abort with parse error, exit 2 |
| Fix for non-auto-fixable check | Abort, exit 2 |
| Fix fails to apply | Abort, exit 1 |
| gh CLI not authenticated | Warn; skip GitHub-live checks; continue |

Exit code 2 = setup/environment error (not a compliance verdict).
Exit code 1 = compliance failure (MUST unresolved) or fix failure.
Exit code 0 = clean or successful emission.
