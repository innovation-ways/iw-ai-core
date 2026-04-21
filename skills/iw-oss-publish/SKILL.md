---
name: iw-oss-publish
version: "0.1.0"
description: >
  Verifies and prepares a private Innovation Ways repository for safe public
  OSS release under a permissive license. Runs secrets/history/license/community
  compliance checks, auto-generates missing files (LICENSE, README, CoC v3,
  CONTRIBUTING with DCO, SECURITY, NOTICE, THIRD_PARTY_LICENSES, gitleaks
  config, pre-commit config, GitHub Actions workflows), and guides the
  flip-to-public workflow with history rewrite. Three modes: scan (audit),
  make_oss (prepare), publish (flip). Use when preparing a repo for OSS
  release, auditing an already-public repo for compliance drift, or when user
  says "release as OSS", "make this public", "OSS compliance check",
  "/iw-oss-publish".
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: <mode: scan|make_oss|publish> [target path, default .]
---

# IW OSS Publish

Safely prepare and publish an Innovation Ways repository as public open-source software.

**Invocation**: `$ARGUMENTS` (mode + optional path)

This skill implements the pre-publish compliance checklist from [R-00061](../../docs/research/R-00061-private-to-public-repo-technical-compliance.md) (technical) and [R-00062](../../docs/research/R-00062-private-to-public-repo-legal-community-compliance.md) (legal/community). Findings map to RFC 2119 severities (MUST / SHOULD / MAY) and to OpenSSF OSPS Baseline controls where applicable.

---

## Three Modes

| Mode | Purpose | Writes files? | Changes history? | Touches GitHub live state? |
|------|---------|---------------|-------------------|-----------------------------|
| `scan` (default) | Audit current compliance posture | No | No | No |
| `make_oss` | Prepare private repo for OSS release | Yes (on a branch) | No | No |
| `publish` | Flip verified repo to public | Yes | Optional (with user approval) | Emits `gh` commands only |

See `references/modes.md` for detailed per-mode walkthroughs.

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

Phase 1 (current): `scan` mode is functional. `make_oss` and `publish` modes are planned for Phases 2 and 3 and will be added as `--mode make_oss` and `--mode publish` arguments on the same script (or a single wrapper).

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
- For `publish` mode: `gh` CLI authenticated against the target GitHub org (`innovation-ways`).

---

## Step 1: Parse Arguments

Extract `mode` and `target_path` from `$ARGUMENTS`:

- If no arguments: mode = `scan`, target = `.` (current directory).
- If first argument is one of `scan` / `make_oss` / `publish`: use it as mode.
- Second argument (if present) is the target path; defaults to `.`.
- Any other argument → reject and show usage.

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
| `project_description` | empty | Falls back to prompting if empty during `make_oss` |
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

## Step 3: Execute Mode

### `scan` mode

Run the full check catalog (`references/checks.md`) read-only. Output:

- `{target}/.iw/oss-publish-report.md` — human-readable Markdown report
- `{target}/.iw/oss-publish-findings.json` — machine-readable findings
- `{target}/.iw/gitleaks.sarif` — uploadable to GitHub Code Scanning
- `{target}/.iw/sbom.spdx.json` + `{target}/.iw/sbom.cyclonedx.json` — if Tier-1 SBOM tools available

Exit code: `1` if any MUST finding is unresolved, `0` otherwise (warnings always printed).

### `make_oss` mode

1. Run `scan` first (read-only).
2. Create a branch `iw-oss-publish/prep-YYYY-MM-DD` in the target repo.
3. Auto-apply fixes per `references/fix_recipes.md`:
   - Generate missing community health files from `templates/` (LICENSE, README stub, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CODEOWNERS, TRADEMARK, PULL_REQUEST_TEMPLATE, ISSUE_TEMPLATE/*, NOTICE for Apache-2.0).
   - Generate/update `.github/workflows/` (scorecard, codeql, release-please, compliance-scan).
   - Generate `.gitleaks.toml` and `.pre-commit-config.yaml`.
   - Regenerate `THIRD_PARTY_LICENSES` via `pip-licenses` / `license-checker` / `go-licenses` per detected ecosystem.
   - Pin action versions via `pinact run`.
   - Add `.iw/oss-publish.toml` with resolved config if missing.
4. Re-run `scan` after fixes.
5. Output:
   - A final `compliance-punchlist.md` with all remaining MUST/SHOULD findings that could not be auto-fixed (require human input: crypto classification, name collision, trademark search, etc.).
   - Stage changes on the branch but **do not commit** — user reviews and commits.

Exit code: `1` if any MUST finding remains unresolved after auto-fix, `0` otherwise.

### `publish` mode

**This mode affects operational outcomes. Every destructive action requires explicit user confirmation.**

1. Run `scan`. **Hard-block** if any MUST finding is unresolved. Direct user to run `make_oss` first.
2. If `history_strategy` config is unset, interactively ask the user: `nuke` / `filter-repo` / `preserve`. See `references/history_rewrite.md` for the decision tree.
3. Print the exact history-rewrite commands for the chosen strategy. **Wait for user to run them manually** — do not execute destructive commands on behalf of the user.
4. Run a final scan of the rewritten repo to verify no secrets leaked into the new history.
5. Emit a `gh`-CLI playbook (`{target}/.iw/publish-playbook.sh`) containing:
   - `gh repo edit` for description/topics/homepage/merge settings.
   - `gh api` PUT for branch protection rules.
   - Secret scanning + push protection enable.
   - Dependabot alerts + security updates enable.
   - Private Vulnerability Reporting enable.
   - Reminder to open a GitHub Support ticket for SHA cache purge if any secrets were found in rewritten history.
6. **Do not execute the playbook** — print it for user review and hand off.

Exit code: `1` on hard-block or history-rewrite verification failure, `0` on successful playbook emission.

---

## Constraints

- **MUST** read `.iw/oss-publish.toml` if present before applying any default.
- **MUST** exit non-zero on unresolved MUST-level findings.
- **MUST NOT** execute destructive git operations (`git-filter-repo`, force-push, `git checkout --orphan`) automatically — always print commands for user execution.
- **MUST NOT** auto-apply GitHub settings that affect live state (branch protection, visibility, webhook changes) — always emit a `gh`-CLI playbook for user review.
- **MUST NOT** commit changes in `make_oss` mode — stage only, let user review.
- **MUST NOT** include the skill's own templates in the compliance scan of the target repo.
- **MUST** treat any crypto-related import as a human-review surface per R-00062 finding #10; never auto-approve crypto compliance.
- **MUST** emit the full 4-artifact disclosure bundle (markdown report, JSON findings, SARIF, SBOM × 2) in every `scan` run regardless of mode context.
- **NEVER** scan or rewrite submodule history — surface submodules as a human-review item.
- **NEVER** operate on a target path that is not a git repository.

---

## Report Template

Final skill output (to console and stored in `.iw/oss-publish-report.md`):

```markdown
## IW OSS Publish — {mode} — {target}

**Date**: {YYYY-MM-DD}
**Target**: {path}
**Mode**: {scan|make_oss|publish}
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
- {what to run next, based on mode and findings}
```
