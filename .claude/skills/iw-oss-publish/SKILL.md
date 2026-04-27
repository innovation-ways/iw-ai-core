---
name: iw-oss-publish
version: "0.2.0"
description: >
  Verifies a private Innovation Ways repository for safe public OSS release.
  Runs secrets/history/license/community compliance checks and auto-generates
  missing files (LICENSE, README, CoC v3, CONTRIBUTING with DCO, SECURITY, NOTICE,
  THIRD_PARTY_LICENSES, gitleaks config, pre-commit config, GitHub Actions workflows).
  Use when auditing an already-public repo for compliance drift, running a compliance
  scan, or when user says "OSS compliance check", "run OSS scan", "/iw-oss-publish".
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: <target path, default .>
---

# IW OSS Publish

Audit and prepare an Innovation Ways repository for public open-source release.

**Invocation**: `$ARGUMENTS` (optional target path)

This skill implements the pre-publish compliance checklist from [R-00061](../../docs/research/R-00061-private-to-public-repo-technical-compliance.md) (technical) and [R-00062](../../docs/research/R-00062-private-to-public-repo-legal-community-compliance.md) (legal/community). Findings map to RFC 2119 severities (MUST / SHOULD / MAY) and to OpenSSF OSPS Baseline controls where applicable.

---

## Mode

Only `scan` mode is supported in Phase A. Per-finding fix invocation will be added in Phase C via `uv run iw oss fix <CHECK_ID> [--apply]`.

| Mode | Purpose | Writes files? | Changes history? | Touches GitHub live state? |
|------|---------|---------------|-------------------|-----------------------------|
| `scan` (default) | Audit current compliance posture | No | No | No |
| `fix` (Phase C) | Per-finding auto-fix | Yes (on branch) | No | No |

---

## Invocation

The skill is a Python orchestrator. Run it directly via Bash:

```bash
# Default: scan current directory
python3 .claude/skills/iw-oss-publish/scripts/scan.py

# Scan a specific repo
python3 .claude/skills/iw-oss-publish/scripts/scan.py --target /path/to/repo

# Verbose logging
python3 .claude/skills/iw-oss-publish/scripts/scan.py --verbose
```

Phase C (per-finding fix):
```bash
uv run iw oss fix <CHECK_ID> [--apply]
```

Exit codes: `0` clean, `1` MUST finding unresolved, `2` setup error, `130` user-cancelled.

Artifacts land in `{target}/.iw/`:
- `oss-publish-report.md` — human-readable report
- `oss-publish-findings.json` — machine-readable findings
- `iw-oss-publish.sarif` — structural findings SARIF
- `gitleaks-tree.sarif` + `gitleaks-history.sarif` — when gitleaks is installed
- `sbom.spdx.json` + `sbom.cyclonedx.json` — when syft is installed
- `grype-vulnerabilities.json` — when grype runs

---

## Prerequisites

- `iw-ai-core` project context is available (reads `.iw/oss-publish.toml` if present, else uses defaults).
- Tool bootstrap completed: run `bash .claude/skills/iw-oss-publish/scripts/install_tools.sh` once per machine. See `references/tools.md` for the Tier 1 (required) and Tier 2 (recommended) lists.

---

## Step 1: Parse Arguments

Extract `target_path` from `$ARGUMENTS`:

- If first argument is a path: use it as target.
- Default target is `.` (current directory).

Reject and abort if the target path is not a git repository (`git rev-parse --git-dir` fails).

---

## Step 2: Load Project Configuration

Read project-level config in order of precedence:

1. `{target}/.iw/oss-publish.toml` if present
2. `[tool.iw.oss-publish]` section of `{target}/pyproject.toml` if present
3. Fall back to IW defaults (from `references/tools.md` "Defaults" table)

Required config keys (with defaults):

| Key | Default | Notes |
|-----|---------|-------|
| `project_name` | repo directory basename | Used in LICENSE, README, NOTICE |
| `project_description` | empty | Falls back to prompting if empty during `fix` |
| `license` | `Apache-2.0` | `MIT` for <500-LOC single-author utilities |
| `company_legal_name` | `Innovation Ways - Unipessoal LDA` | Used in LICENSE/NOTICE — full legal form |
| `company_brand` | `Innovation Ways` | Used in README/TRADEMARK.md — short form |
| `company_github_org` | `innovation-ways` | GitHub org path |
| `company_contact_email` | `info@innovation-ways.com` | SECURITY / CoC / trademark contact |
| `homepage` | `https://innovation-ways.com` | Repo homepage URL |
| `contributor_agreement` | `DCO` | `CLA` only for open-core projects |
| `coc_version` | `v3` | `v2.1` acceptable for existing repos |
| `sbom_formats` | `["spdx", "cyclonedx"]` | Both emitted by default |
| `history_strategy` | unset | `nuke` / `filter-repo` / `preserve` — asked interactively if unset |

Any config key may be overridden inline via `--<key> <value>` flags (CLI only, not documented here — see `references/modes.md`).

---

## Step 3: Execute Scan

Run the full check catalog (`references/checks.md`) read-only. Output:

- `{target}/.iw/oss-publish-report.md` — human-readable Markdown report
- `{target}/.iw/oss-publish-findings.json` — machine-readable findings
- `{target}/.iw/gitleaks.sarif` — uploadable to GitHub Code Scanning
- `{target}/.iw/sbom.spdx.json` + `{target}/.iw/sbom.cyclonedx.json` — if Tier-1 SBOM tools available

Exit code: `1` if any MUST finding is unresolved, `0` otherwise (warnings always printed).

---

## Constraints

- **MUST** read `.iw/oss-publish.toml` if present before applying any default.
- **MUST** exit non-zero on unresolved MUST-level findings.
- **MUST NOT** execute git operations beyond `git status` / `git rev-parse` — no commits, no branch switches, no worktree operations.
- **MUST NOT** switch branches under any circumstances.
- **MUST NOT** execute destructive git operations (`git-filter-repo`, force-push, `git checkout --orphan`) automatically — always print commands for user execution.
- **MUST NOT** auto-apply GitHub settings that affect live state (branch protection, visibility, webhook changes) — always emit a `gh`-CLI playbook for user review.
- **MUST NOT** include the skill's own templates in the compliance scan of the target repo.
- **MUST** treat any crypto-related import as a human-review surface per R-00062 finding #10; never auto-approve crypto compliance.
- **MUST** emit the full 4-artifact disclosure bundle (markdown report, JSON findings, SARIF, SBOM × 2) in every `scan` run.
- **NEVER** scan or rewrite submodule history — surface submodules as a human-review item.
- **NEVER** operate on a target path that is not a git repository.

---

## Report Template

Final skill output (to console and stored in `.iw/oss-publish-report.md`):

```markdown
## IW OSS Publish — scan — {target}

**Date**: {YYYY-MM-DD}
**Target**: {path}
**Mode**: scan
**License**: {SPDX-ID}
**Visibility**: {private|public}
**Tools available**: {list of tools detected / missing}

### Blockers (MUST)
- {check_id}: {summary} — {remediation hint}

### Warnings (SHOULD)
- {check_id}: {summary} — {remediation hint}

### Info (MAY)
- {check_id}: {summary}

### Human judgment required
- {check_id}: {question for the user}

### Artifacts emitted
- {path} — description

### Next step
- Run `uv run iw oss fix <CHECK_ID> --apply` for per-finding fixes (Phase C)
```